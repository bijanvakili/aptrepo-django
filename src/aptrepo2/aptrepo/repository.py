import gzip
import hashlib
import os
from django.conf import settings
from debian_bundle import deb822, debfile
import pyme.core
import pyme.constants.sig
import models, common

# TODO enforce exclusive access for all write operations
# TODO implement caching of metadata instead of writing to disk

class Repository:
    """
    Manages the apt repository including all packages and associated metadata
    """

    _RELEASE_FILENAME = 'Release'
    _PACKAGES_FILENAME = 'Packages'
    _BINARYPACKAGES_PREFIX = 'binary-'
    
    def __init__(self):
        # publish the GPG public key
        gpg_context = self._load_gpg_context()
        gpg_publickey_path = os.path.join(settings.MEDIA_ROOT, settings.APTREPO_FILESTORE['gpg_publickey'])
        if not os.path.exists(gpg_publickey_path):
            public_key_data = pyme.core.Data()
            gpg_context.op_export(None, 0, public_key_data)
            with open(gpg_publickey_path, 'wt') as publickey_fh:
                public_key_data.seek(0, 0)
                publickey_fh.write(public_key_data.read())
                

    def add_package(self, distribution_name, section_name, package_file):
        """
        Add a package to the repository
        
        distribution_name - distribution to add package
        section_name - section within distribution to add package
        package_file - instance of TemporaryUploadedFile
        """
        # check preconditions
        (_, ext) = os.path.splitext(package_file.name)
        if ext != '.deb':
            raise common.AptRepoException('Invalid extension: {0}'.format(ext))        
        distribution = models.Distribution.objects.get(name=distribution_name)
        section = models.Section.objects.get(name=section_name, 
                                             distribution__name=distribution_name)
        
        # extract control file information for denormalized searches
        # NOTE: package_file must be of type TemporaryUploadedFile because the DebFile()
        #       class cannot django file types and must use direct filenames.
        deb = debfile.DebFile(filename=package_file.temporary_file_path())
        control = deb.debcontrol()
        if control['Architecture'] not in distribution.get_architecture_list():
            raise common.AptRepoException(
                'Invalid architecture for distribution ({0}) : {1}'.format(
                    distribution_name, control['Architecture']))

        # compute hashes
        hashes = {}
        hashes['md5'] = common.hash_file_by_fh(hashlib.md5(), package_file)
        hashes['sha1'] = common.hash_file_by_fh(hashlib.sha1(), package_file)
        hashes['sha256'] = common.hash_file_by_fh(hashlib.sha256(), package_file)

        # create a new package entry or verify its hashes if it already exists
        package_search = models.Package.objects.filter(package_name=control['Package'],
                                                       version=control['Version'],
                                                       architecture=control['Architecture'])
        if package_search.count() > 0:
            package = package_search[0]
            if package.hash_md5 != hashes['md5'] or \
               package.hash_sha1 != hashes['sha1'] or \
               package.hash_sha256 != hashes['sha256']:
                raise common.AptRepoException(
                    '({0}, {1}, {2}) already exist with different file contents'.format(
                        package.package_name, package.version, package.architecture))
        else:
            package = models.Package()
            try:
                package.size = package_file.size
                package.hash_md5 = hashes['md5']
                package.hash_sha1 = hashes['sha1']
                package.hash_sha256 = hashes['sha256']
    
                package.architecture = control['Architecture']
                package.package_name = control['Package']
                package.version = control['Version']
                package.control = control.dump()
                
                hash_prefix = hashes['md5'][0:settings.APTREPO_FILESTORE['hash_depth']]
                stored_file_path = os.path.join(settings.APTREPO_FILESTORE['packages_subdir'], 
                                               hash_prefix, package_file.name)
                package.path.save(stored_file_path, package_file) 
                
                package.save()
                
            except Exception as e:
                if package.path.name:
                    package.path.delete(package.path.name)
                raise e

        # create a package instance
        # TODO set the creator
        package_instance, _ = models.PackageInstance.objects.get_or_create(
            package=package, section=section)
        
        # update repo metadata(recreate=false, distribution, section, architecture)
        self._update_metadata(update_packages=True, 
                              distribution=distribution_name,
                              section=section_name,
                              architecture=package.architecture)
        
        # insert action
        models.Action.objects.create(instance=package_instance, action=models.Action.UPLOAD,
                                     user=package_instance.creator) 

        
    def remove_package(self, distribution, section, package_name, architecture, version):
        # TODO implement the remove package operation
        pass
    

    def _update_metadata(self, update_packages=False, update_release=True, **kwargs):
        """
        Update of repository metadata (recursive)
        
        update_packages - Flag indicating whether to recreate Packages file(s)
        update_release  - Flag indicating whether to recreate Release file(s)
        
        Optional keyword arguments include:
        
        distribution - Update only a single distribution
        section      - Update only a single section (distribution must be specified)
        architecture - Update only an architecture set (distribution and section must be specified) 
        """
        # determine which distributions are involved in this update        
        distributions = None
        if kwargs.has_key('distribution'):
            distributions = models.Distribution.objects.filter(name=kwargs['distribution'])
        else:
            distributions = models.Distribution.objects.all()
        
        # update any Packages files as necessary
        if update_packages:
            if kwargs.has_key('architecture'):
                self._update_package_list(kwargs['distribution'], 
                                          kwargs['section'], 
                                          kwargs['architecture'])
                
            elif kwargs.has_key('section'):    
                architectures = distributions[0].get_architecture_list()
                for architecture in architectures:
                    self._update_metadata(update_packages=True, update_release=False,
                                          distribution=kwargs['distribution'], 
                                          section=kwargs['section'], 
                                          architecture=architecture)
                    
            elif kwargs.has_key('distribution'):
                sections = models.Section.objects.filter(distribution=distributions[0])
                for section in sections:
                    self._update_metadata(update_packages=True, update_release=False,
                                          distribution=kwargs['distribution'], 
                                          section=section.name)
                    
            else:
                for distribution in distributions:
                    self._update_metadata(update_packages=True, update_release=False,
                                          distribution=distribution.name)
        
        # update any Release files as necessary
        if update_release:
            for distribution in distributions:
                self._update_release_list(distribution.name)            
    
    
    def write_package_list(self, fh, distribution, section, architecture):
        """
        Updates a Debian 'Packages' file for a subsection of the repository
        by writing to a filehandle (fh)
        """
        
        # update the Packages file
        package_instances = models.PackageInstance.objects.filter(section__distribution__name=distribution,
                                                                  section__name=section,
                                                                  package__architecture=architecture)
        for instance in package_instances:
            control_data = deb822.Deb822(sequence=instance.package.control)
            control_data['Filename'] = instance.package.path.name
            control_data['MD5sum'] = instance.package.hash_md5
            control_data['SHA1'] = instance.package.hash_sha1
            control_data['SHA256'] = instance.package.hash_sha256
            
            control_data.dump(fh)
            fh.write('\n')
                
   
    def _update_release_list(self, distribution_name):
        """
        Updates a Debian 'Releases' file for a single distribution
        """
        distribution = models.Distribution.objects.get(name=distribution_name)
        
        # create new release with standard data
        release = {}
        release['Origin'] = distribution.origin
        release['Label'] = distribution.label
        release['Codename'] = distribution.name
        release['Date'] = distribution.creation_date.strftime('%a, %d %b %Y %H:%M:%S %z UTC')
        release['Description'] = distribution.description
        release['Architectures'] = ' '.join(distribution.get_architecture_list())
        release['Components'] = ' '.join(models.Section.objects.filter(
            distribution__name=distribution_name).values_list('name', flat=True))

        release_path_prefix = os.path.join(settings.APTREPO_FILESTORE['metadata_subdir'], 
                                           distribution_name)
        metafiles = models.UniqueFile.objects.filter(path__startswith=release_path_prefix)
        release_filename = os.path.join(settings.MEDIA_ROOT, 
                                        release_path_prefix, 
                                        self._RELEASE_FILENAME)
        release_hash_entries = {'MD5Sum':[], 'SHA1':[], 'SHA256':[]}
        with open(release_filename, 'wt') as release_fh:            
            for k,v in release.items():
                release_fh.write('{0}: {1}\n'.format(k, v))
            
            for metafile in metafiles:
                metafile_path = str(metafile.path).replace(release_path_prefix + '/', '', 1)
                release_hash_entries['MD5Sum'].append(
                    ' {0} {1} {2}'.format(metafile.hash_md5, metafile.size, metafile_path)
                )
                release_hash_entries['SHA1'].append(
                    ' {0} {1} {2}'.format(metafile.hash_sha1, metafile.size, metafile_path)
                )
                release_hash_entries['SHA256'].append(
                    ' {0} {1} {2}'.format(metafile.hash_sha256, metafile.size, metafile_path)
                )
                
            for hash_type, hash_list in release_hash_entries.items():
                release_fh.write(hash_type + ':\n')
                release_fh.write('\n'.join(hash_list) + '\n')
                
        # GPG sign the release file
        # (use ASCII filenames as Unicode not currently supported)
        release_plain_data = pyme.core.Data(file=release_filename.encode('ascii', 'ignore'))
        release_signature_data = pyme.core.Data()
        modes = pyme.constants.sig.mode
        gpg_context = self._load_gpg_context()
        sign_result = gpg_context.op_sign(release_plain_data, 
                                          release_signature_data,
                                          modes.DETACH)
        pyme.errors.errorcheck(sign_result)
        release_signature_data.seek(0, 0)
        with open(release_filename + '.gpg', 'wt') as release_gpg_fh:
            release_gpg_fh.write(release_signature_data.read())
    
    
    def _set_unique_file(self, filename):
        """
        Updates or creates a unique file entry in the database
        """
        abs_filename = os.path.join(settings.MEDIA_ROOT, filename)
        unique_file, _ = models.UniqueFile.objects.get_or_create(path=filename)
        unique_file.size = os.path.getsize(abs_filename)
        unique_file.hash_md5 = common.hash_file(hashlib.md5(), abs_filename)
        unique_file.hash_sha1 = common.hash_file(hashlib.sha1(), abs_filename)
        unique_file.hash_sha256 = common.hash_file(hashlib.sha256(), abs_filename)
        unique_file.save()
        
        return unique_file

    def _load_gpg_context(self):
        """
        Load a gpgme context with the repo GPG private key
        """
        gpg_context = pyme.core.Context()
        gpg_context.set_armor(1)
        gpg_context.signers_clear()
        private_key_data = pyme.core.Data(file=settings.GPG_SECRET_KEY)
        gpg_context.op_import(private_key_data)
        gpgme_result = gpg_context.op_import_result()
        pyme.errors.errorcheck(gpgme_result.imports[0].result)
        
        return gpg_context
