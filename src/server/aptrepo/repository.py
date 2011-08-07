import gzip
import hashlib
import os
import shutil
import struct
import tempfile
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from debian_bundle import deb822, debfile
import pyme.core
import pyme.constants.sig
import models, common

class Repository:
    """
    Manages the apt repository including all packages and associated metadata
    """

    _RELEASE_FILENAME = 'Release'
    _PACKAGES_FILENAME = 'Packages'
    _BINARYPACKAGES_PREFIX = 'binary'
    _ARCHITECTURE_ALL = 'all'
    
    def get_gpg_public_key(self):
        """
        Retrieves the GPG public key as ASCII text
        """
        cache_key = settings.APTREPO_FILESTORE['gpg_publickey']
        gpg_public_key = cache.get(cache_key)
        if gpg_public_key:
            return gpg_public_key
        
        # return the GPG public key as ASCII text
        gpg_context = self._load_gpg_context()
        public_key_data = pyme.core.Data()
        gpg_context.op_export(None, 0, public_key_data)
        public_key_data.seek(0, 0)
        gpg_public_key = public_key_data.read()
        
        cache.set(cache_key, gpg_public_key)
        return gpg_public_key

    
    def get_packages(self, distribution, section, architecture, compressed=False):
        """
        Retrieve the packages data
        """
        packages_path = self._get_packages_path(distribution, section, architecture)
        if compressed:
            packages_path = packages_path + common.GZIP_EXTENSION
        packages_data = cache.get(packages_path)
        if not packages_data:
            self._refresh_releases_data(distribution)
            packages_data = cache.get(packages_path)
            
        return packages_data

    
    def get_release_data(self, distribution):
        """
        Retrieve the release data
        """
        releases_path = self._get_releases_path(distribution)
        releases_data = None
        releases_signature = None
        cached_data = cache.get(releases_path)
        if not cached_data:
            (releases_data, releases_signature) = self._refresh_releases_data(distribution)
        else:
            (releases_data, releases_signature) = cached_data
            
        return (releases_data, releases_signature)            
        

    def add_package(self, distribution_name, section_name, package_file):
        """
        Add a package to the repository
        
        distribution_name - distribution to add package
        section_name - section within distribution to add package
        package_file - instance of TemporaryUploadedFile
        
        Returns the new instance id
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
        if control['Architecture'] != self._ARCHITECTURE_ALL and \
            control['Architecture'] not in distribution.get_architecture_list():
            
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
        
        # insert action
        models.Action.objects.create(section=section, action=models.Action.UPLOAD,
                                     user=package_instance.creator)
        
        self._clear_cache(distribution_name)
        return package_instance.id
        
    def clone_package(self, dest_distribution_name, dest_section_name, package_id=None, instance_id=None):
        """
        Clones a package to create another instance
        """
        
        # locate the target section and the source package
        target_section = models.Section.objects.get(distribution__name=dest_distribution_name, 
                                                    name=dest_section_name)
        src_package = None
        if package_id:
            src_package=models.Package.objects.get(package_id)
        elif instance_id:
            src_instance=models.PackageInstance.objects.get(instance_id)
            if src_instance.section.id == target_section.id:
                raise common.AptRepoException('Cannot clone into the same section')
            src_package=src_instance.package
        
        # create the new instance
        # TODO set the creator
        package_instance = models.PackageInstance.objects.create(package=src_package,
                                                                 section=target_section)
        
        # insert action
        models.Action.objects.create(section=target_section, action=models.Action.COPY,
                                     user=package_instance.creator)
        
        self._clear_cache(dest_distribution_name)
        return package_instance.id

        
    def remove_package(self, package_instance_id):
        """
        Removes a package instance

        If there are no instances referencing the actual package, it will be removed as well
        """
        
        # remove the instance
        package_instance = models.PackageInstance.objects.get(id=package_instance_id)
        package_id = package_instance.package.id 
        package_instance.delete()

        # remove the referenced package if it no longer exists
        package_reference_count = models.PackageInstance.objects.filter(package__id=package_id).count()
        package = models.Package.objects.get(id=package_id)
        if package_reference_count == 0:
            package.delete()
        
        # update for the package list for the specific section and architecture
        section = models.Section.objects.get(name=package_instance.section.name)
        self._clear_cache(section.distribution.name)
        
        # insert action
        # TODO change to include request user
        models.Action.objects.create(section=section, action=models.Action.DELETE,
                                     user="who?")
        
        
    def remove_all_package_instances(self, package_id):
        """
        Removes all instances of a package
        """
        instances = models.PackageInstance.objects.filter(package__id=package_id)
        for instance in instances:
            self.remove_package(package_instance_id=instance.id)

    
    def get_actions(self, distribution_id=None, section_id=None, 
                    min_ts=None, max_ts=None):
        """
        Retrieves repository actions
        """
        # construct query based on restrictions
        query_args = []
        if distribution_id:
            query_args.append(Q(section__distribution__id=distribution_id))
        if section_id:
            query_args.append(Q(section__id=section_id))
        if min_ts:
            query_args.append(Q(timestamp__gte=min_ts))
        if max_ts:
            query_args.append(Q(timetsamp__lte=max_ts))
            
        # execute the query and return the result
        actions = models.Action.objects.filter(*query_args).order_by('timestamp')
        return actions
        
    
    def _write_package_list(self, fh, distribution, section, architecture):
        """
        Writes a package list for a repository section
        """
        package_instances = models.PackageInstance.objects.filter(
                                                                  Q(section__distribution__name=distribution),
                                                                  Q(section__name=section),
                                                                  Q(package__architecture=architecture) | 
                                                                  Q(package__architecture=self._ARCHITECTURE_ALL))
        for instance in package_instances:
            control_data = deb822.Deb822(sequence=instance.package.control)
            control_data['Filename'] = instance.package.path.name
            control_data['MD5sum'] = instance.package.hash_md5
            control_data['SHA1'] = instance.package.hash_sha1
            control_data['SHA256'] = instance.package.hash_sha256
            control_data['Size'] = str(instance.package.size)
            
            control_data.dump(fh)
            fh.write('\n')
        
   
    def _refresh_releases_data(self, distribution_name):
        """
        Computes and caches the metadata files for a distribution 
        """
        
        distribution = models.Distribution.objects.get(name=distribution_name)
        sections = models.Section.objects.filter(distribution=distribution).values_list('name', flat=True)
        architectures = distribution.get_architecture_list()

        # create new release with header        
        release = {}
        release['Origin'] = distribution.origin
        release['Label'] = distribution.label
        release['Codename'] = distribution.name
        release['Date'] = distribution.creation_date.strftime('%a, %d %b %Y %H:%M:%S %z UTC')
        release['Description'] = distribution.description
        release['Architectures'] = ' '.join(architectures)
        release['Components'] = ' '.join(sections)

        hash_types = ['MD5Sum', 'SHA1', 'SHA256']
        release_hashes = {}
        for h in hash_types:
            release_hashes[h] = []

        release_data = []
        for k,v in release.items():
            release_data.append('{0}: {1}'.format(k, v))
            
        # compute hashes for all package lists
        tmp_fh = None
        compressed_fh = None
        try:
            tmp_fd, tmp_filename = tempfile.mkstemp(prefix=self._PACKAGES_FILENAME)
            compressed_filename = tmp_filename + common.GZIP_EXTENSION
            tmp_fh = os.fdopen(tmp_fd, 'wb+')
            compressed_fh = open(compressed_filename, 'wb+')
            
            for section in sections:
                for architecture in architectures:

                    # create the Packages file            
                    tmp_fh.seek(0)
                    tmp_fh.truncate(0)
                    self._write_package_list(tmp_fh, distribution_name, section, 
                                             architecture)
                    tmp_fh.flush()
                    tmp_file_size = tmp_fh.tell()
                    
                    # create the compressed version using a timestamp (mtime) of 0
                    # 
                    # TODO Remove conditions around mtime once python v2.7 becomes the minimum 
                    # supported version
                    compressed_fh.seek(0)
                    compressed_fh.truncate(0)
                    gzip_params = {
                                   'filename':self._PACKAGES_FILENAME, 'mode':'wb', 'compresslevel':9, 
                                   'fileobj':compressed_fh}
                    if common.get_python_version() >= 2.7:
                        gzip_params['mtime'] = 0 
                    
                    gzip_fh = gzip.GzipFile(**gzip_params)
                    tmp_fh.seek(0)
                    shutil.copyfileobj(fsrc=tmp_fh, fdst=gzip_fh)
                    gzip_fh.close()
                    compressed_file_size = compressed_fh.tell()

                    # for python v2.6 and earlier, we need to manually set the mtime field to
                    # zero.  This starts at position 4 of the file (see RFC 1952)                    
                    if common.get_python_version() < 2.7:
                        compressed_fh.seek(4)
                        compressed_fh.write(struct.pack('<i',0))

                    packages_path = self._get_packages_path(distribution_name, section, architecture)
                    rel_packages_path = self._get_packages_relative_path(section, architecture)
                    tmp_fh.seek(0)
                    cache.set( packages_path, tmp_fh.read() )
                    compressed_fh.seek(0)
                    cache.set( packages_path + common.GZIP_EXTENSION, compressed_fh.read(compressed_file_size) )
                    
                    # hash the package list for each hash function
                    for type in hash_types:
                        release_hashes[type].append(
                            ' {0} {1} {2}'.format(common.hash_file_by_fh(self._get_hashfunc(type), tmp_fh), 
                                                  tmp_file_size, 
                                                  rel_packages_path))
                        release_hashes[type].append(
                            ' {0} {1} {2}'.format(common.hash_file_by_fh(self._get_hashfunc(type), compressed_fh), 
                                                  compressed_file_size, 
                                                  rel_packages_path + common.GZIP_EXTENSION))

        finally:                        
            if tmp_fh:
                tmp_fh.close()
            if compressed_fh:
                compressed_fh.close()
            os.remove(tmp_filename)
            if os.path.exists(compressed_filename):
                os.remove(compressed_filename)
                    
        for hash_type, hash_list in release_hashes.items():
            release_data.append(hash_type + ':')
            release_data.extend( hash_list )
                
        # create GPG signature for release data
        release_contents = '\n'.join(release_data)
        release_plain_data = pyme.core.Data(release_contents)
        release_signature_data = pyme.core.Data()
        modes = pyme.constants.sig.mode
        gpg_context = self._load_gpg_context()
        sign_result = gpg_context.op_sign(release_plain_data, 
                                          release_signature_data,
                                          modes.DETACH)
        pyme.errors.errorcheck(sign_result)
        release_signature_data.seek(0, 0)
        release_signature = release_signature_data.read()
        
        releases_path = self._get_releases_path(distribution)
        cache.set(releases_path, (release_contents, release_signature) )
        
        return (release_contents, release_signature)


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

    
    def _clear_cache(self, distribution_name):
        distribution = models.Distribution.objects.get(name=distribution_name)
        sections = models.Section.objects.filter(distribution=distribution).values_list('name', flat=True)
        architectures = distribution.get_architecture_list()
        
        for section in sections:
            for architecture in architectures:
                packages_path = self._get_packages_path(distribution_name, section, architecture)
                cache.delete_many([ packages_path, packages_path + common.GZIP_EXTENSION ])
        
        releases_path = self._get_releases_path(distribution_name)
        cache.delete_many([releases_path, releases_path + common.GPG_EXTENSION])


    def _get_packages_path(self, distribution, section, architecture):
        packages_path = '{0}/{1}/{2}'.format(
            settings.APTREPO_FILESTORE['metadata_subdir'],
            distribution, 
            self._get_packages_relative_path(section, architecture))
        return packages_path
    

    def _get_packages_relative_path(self, section, architecture):
        packages_path = '{0}/{1}-{2}/{3}'.format(
            section, self._BINARYPACKAGES_PREFIX, architecture, 
            self._PACKAGES_FILENAME)
        return packages_path


    def _get_releases_path(self, distribution):
        releases_path = '{0}/{1}/{2}'.format(
            settings.APTREPO_FILESTORE['metadata_subdir'],
            distribution, self._RELEASE_FILENAME)
        return releases_path
    
    
    def _get_hashfunc(self, hash_name):
        name = hash_name.lower()
        if name == 'md5' or name == 'md5sum':
            return hashlib.md5()
        elif name == 'sha1':
            return hashlib.sha1()
        elif name == 'sha256':
            return hashlib.sha256()
