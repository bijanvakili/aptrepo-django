import gzip
import hashlib
import logging
import os
import shutil
import struct
import tempfile
from django.conf import settings
from django.core.cache import cache
from django.core.files import File
from django.db.models import Q
from debian_bundle import deb822, debfile
from apt_pkg import version_compare
from server.aptrepo import models
from server.aptrepo.util import AptRepoException, constants
from server.aptrepo.util.hash import hash_file_by_fh, GPGSigner
from server.aptrepo.util.system import get_python_version

class Repository():
    """
    Manages the apt repository including all packages and associated metadata
    """

    _BINARYPACKAGES_PREFIX = 'binary'
    _ARCHITECTURE_ALL = 'all'
    _RELEASE_FILENAME = 'Release'
    _PACKAGES_FILENAME = 'Packages'
    _DEBIAN_EXTENSION = '.deb'
        
    def __init__(self, logger=None):
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(settings.DEFAULT_LOGGER)
        
    def get_gpg_public_key(self):
        """
        Retrieves the GPG public key as ASCII text
        """
        # attempt to retrieve the public key from the cache
        cache_key = settings.APTREPO_FILESTORE['gpg_publickey']
        gpg_public_key = cache.get(cache_key)
        if gpg_public_key:
            return gpg_public_key
        
        # return the GPG public key as ASCII text
        gpg_signer = GPGSigner()
        gpg_public_key = gpg_signer.get_public_key()
        
        cache.set(cache_key, gpg_public_key)
        return gpg_public_key

    
    def get_packages(self, distribution, section, architecture, compressed=False):
        """
        Retrieve the Debian 'Packages' data
        
        distribution - name of distribution
        section - name of section
        architecture - specifies the architecture subset of packages
        compressed - (optional) if true, will compress with gzip
        """
        packages_path = self._get_packages_path(distribution, section, architecture)
        if compressed:
            packages_path = packages_path + constants.GZIP_EXTENSION
        packages_data = cache.get(packages_path)
        if not packages_data:
            self._refresh_releases_data(distribution)
            packages_data = cache.get(packages_path)
            
        return packages_data

    
    def get_release_data(self, distribution):
        """
        Retrieve the Debian 'Release' data
        
        distribution - name of distribution
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
        

    def add_package(self, **kwargs):
        """
        Add a package to the repository

        section    - section model object 
        OR        
        section_id - unique ID of the section (optional)
        OR
        distribution_name - distribution to add package (if section_id is not specified)
        section_name - section within distribution to add package (if section_id is not specified)
        
        uploaded_package_file - instance of Django TemporaryUploadedFile
        OR
        package_fh   - instance of file
        package_path - pathname to package
        package_size - size of package file
        
        Returns the new instance id
        """
        # parse the arguments
        distribution = None
        if 'section' in kwargs:
            section = kwargs['section']
        elif 'section_id' in kwargs:
            section = models.Section.objects.get(pk=kwargs['section_id'])
        elif 'distribution_name' in kwargs and 'section_name' in kwargs:
            distribution = models.Distribution.objects.get(name=kwargs['distribution_name'])            
            section = models.Section.objects.get(name=kwargs['section_name'], 
                                                 distribution=distribution)
        else:
            raise AptRepoException('No section argument specified')
        
        if not distribution:
            distribution = section.distribution

        if 'uploaded_package_file' in kwargs:
            package_fh = kwargs['uploaded_package_file']
            package_path = kwargs['uploaded_package_file'].temporary_file_path()
            package_name = kwargs['uploaded_package_file'].name            
            package_size = kwargs['uploaded_package_file'].size
        else:
            package_fh = File(kwargs['package_fh'])
            package_path = kwargs['package_path']
            (_, package_name) = os.path.split(package_path)
            package_size = kwargs['package_size']
        
        # check preconditions
        (_, ext) = os.path.splitext(package_name)
        if ext != self._DEBIAN_EXTENSION:
            raise AptRepoException('Invalid extension: {0}'.format(ext))        

        # extract control file information for denormalized searches
        deb = debfile.DebFile(filename=package_path)
        control = deb.debcontrol()
        if control['Architecture'] != self._ARCHITECTURE_ALL and \
            control['Architecture'] not in distribution.get_architecture_list():
            
            raise AptRepoException(
                'Invalid architecture for distribution ({0}) : {1}'.format(
                    distribution.name, control['Architecture']))

        # compute hashes
        hashes = {}
        hashes['md5'] = hash_file_by_fh(hashlib.md5(), package_fh)
        hashes['sha1'] = hash_file_by_fh(hashlib.sha1(), package_fh)
        hashes['sha256'] = hash_file_by_fh(hashlib.sha256(), package_fh)

        # create a new package entry or verify its hashes if it already exists
        package_search = models.Package.objects.filter(package_name=control['Package'],
                                                       version=control['Version'],
                                                       architecture=control['Architecture'])
        if package_search.count() > 0:
            package = package_search[0]
            if package.hash_md5 != hashes['md5'] or \
               package.hash_sha1 != hashes['sha1'] or \
               package.hash_sha256 != hashes['sha256']:
                raise AptRepoException(
                    '({0}, {1}, {2}) already exist with different file contents'.format(
                        package.package_name, package.version, package.architecture))
        else:
            package = models.Package()
            try:
                package.size = package_size
                package.hash_md5 = hashes['md5']
                package.hash_sha1 = hashes['sha1']
                package.hash_sha256 = hashes['sha256']
    
                package.architecture = control['Architecture']
                package.package_name = control['Package']
                package.version = control['Version']
                package.control = control.dump()
                
                hash_prefix = hashes['md5'][0:settings.APTREPO_FILESTORE['hash_depth']]
                stored_file_path = os.path.join(settings.APTREPO_FILESTORE['packages_subdir'],
                    hash_prefix, '{0}_{1}_{2}{3}'.format(control['Package'], 
                                                          control['Version'], 
                                                          control['Architecture'],
                                                          self._DEBIAN_EXTENSION))
                package.path.save(stored_file_path, package_fh) 
                
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
        
        self._clear_cache(distribution.name)
        return package_instance.id
        
    def import_dir(self, section_id, dir_path, 
                   dry_run=False, recursive=False, ignore_errors=False):
        """
        Imports a directory of Debian packages
        
        section_id - integer primary key (id) specifying the section ti import packages
        dir_path - root directory containing Debian packages to import
        dry_run - (optional) if true, will only output import actions to logger but not apply changes
        recursive - (optional) if true, inspect packages in subdirectories
        ignore_errors - (optional) if true, continues importing packages even if any fail
        """

        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                if filename.endswith(self._DEBIAN_EXTENSION):
                    try:
                        package_path = os.path.join(dir_path, root, filename) 
                        if not dry_run:
                            with open(package_path, 'r') as package_file:
                                self.add_package(section_id=section_id, package_fh=package_file,
                                                 package_path=package_path, 
                                                 package_size=os.path.getsize(package_path))
                        self.logger.info('Imported ' + package_path)
                        
                    except Exception as e:
                        if not ignore_errors:
                            raise e
                        else:
                            self.logger.warning(e)

            if not recursive:
                del dirs[:]
        
    def clone_package(self, dest_section, package_id=None, instance_id=None):
        """
        Clones a package to create another instance
        
        dest_section - destination section (model)
        
        package_id - primary key (id) of package from which to create a new instance
        OR
        instance_id - primary key (id) of an existing instance to copy
        
        Returns the new instance id
        """
        # locate the target section and the source package
        src_package = None
        if package_id:
            src_package=models.Package.objects.get(package_id)
        elif instance_id:
            src_instance=models.PackageInstance.objects.get(instance_id)
            if src_instance.section.id == dest_section.id:
                raise AptRepoException('Cannot clone into the same section')
            src_package=src_instance.package
        
        # create the new instance
        # TODO set the creator
        package_instance = models.PackageInstance.objects.create(package=src_package,
                                                                 section=dest_section)
        
        # insert action
        models.Action.objects.create(section=dest_section, action=models.Action.COPY,
                                     user=package_instance.creator)
        
        self._clear_cache(dest_section.distribution.name)
        return package_instance.id

        
    def remove_package(self, package_instance_id):
        """
        Removes a package instance
        If there are no instances referencing the actual package, it will be removed as well
        
        package_instance_id - primary key (id) of package to remove
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
        
        package_instance_id - primary key (id) of package to remove        
        """
        instances = models.PackageInstance.objects.filter(package__id=package_id)
        for instance in instances:
            self.remove_package(package_instance_id=instance.id)

    
    def get_actions(self, distribution_id=None, section_id=None, 
                    min_ts=None, max_ts=None):
        """
        Retrieves repository actions
        
        distribution_id - distribution from which to retrieve actions
        OR
        section_id - section from which to retrieve actions
        
        min_ts - (optional) minimum timestamp for oldest action
        max_ts - (opitonal) maximum timetsamp for newest action
        
        Returns a list of actions
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
        
    
    def prune_sections(self, section_id_list, dry_run=False):
        """
        Prunes packages from the selected sections
        
        section_id_list - list of section ids in which to prune packages
        dry_run - (optional) if true, will only log changes but will not apply them 
        
        Returns a tuple containing:
        - total instances pruned 
        - total packages pruned
        - total actions pruned 
        """
        total_instances_pruned = 0
        total_actions_pruned = 0
        for section_id in section_id_list:
            
            # skip the section if it doesn't require pruning
            section = models.Section.objects.get(id=section_id)
            if section.package_prune_limit > 0:

                # run bulk query for all package instances in this section and ensure their package information 
                # is available for a sequential analysis. Note that we cannot sort by version because a simple 
                # lexical comparison will not meet Debian standards.  
                instances = models.PackageInstance.objects.filter(section=section)
                instances = instances.select_related('package__package_name',
                                                     'package__architecture',
                                                     'package__version')
                instances = instances.order_by('package__package_name', 'package__architecture')
                
                instance_ids_to_remove = []
                (curr_name, curr_architecture) = (None, None)
                curr_instances = []
                for instance in instances:
                    
                    # reset the count if this is a new (name,architecture) pair
                    if instance.package.package_name != curr_name or \
                        instance.package.architecture != curr_architecture:
    
                        # determine which packages to prune
                        instance_ids_to_remove += Repository._find_pruneable_instances(curr_instances,
                                                                                       section.package_prune_limit)
    
                        # reset for next group                
                        curr_name = instance.package.package_name
                        curr_architecture = instance.package.architecture
                        curr_instances = []
                    
                    # add to current instance set
                    curr_instances.append(instance)
    
                # final review of pruneable instances
                instance_ids_to_remove += Repository._find_pruneable_instances(curr_instances,
                                                                               section.package_prune_limit)
                    
                # remove the instances
                num_instances_pruned = len(instance_ids_to_remove)
                for instance_id in instance_ids_to_remove:
                    instance = models.PackageInstance.objects.get(id=instance_id)
                    
                    # avoid logging to debug unless required since it requires a SQL join operation
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug('Pruning instance (%s,%s,%s) from %s:%s',
                                     instance.package.package_name,
                                     instance.package.architecture,
                                     instance.package.version,
                                     section.distribution.name,
                                     section.name)
                    if not dry_run:
                        instance.delete()
                    
                self.logger.info('%d instances pruned from section %s:%s', 
                            num_instances_pruned,
                            section.distribution.name, 
                            section.name)
                total_instances_pruned += num_instances_pruned
                
            # prune actions for the section            
            if section.action_prune_limit > 0:
                actions_to_prune = models.Action.objects.filter(section=section)
                actions_to_prune = actions_to_prune.order_by('-timestamp')[section.action_prune_limit:]
                
                num_actions_pruned = 0
                for action in actions_to_prune:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug('Pruning action (%s)', action)
                    if not dry_run:
                        action.delete()
                    num_actions_pruned += 1

                self.logger.info('%d actions pruned from section %s:%s', 
                            num_actions_pruned,
                            section.distribution.name, 
                            section.name)
                total_actions_pruned += num_actions_pruned
            
        
        # prune any associated package files by locating all Package objects that have
        # no associated PackageInstance (a LEFT OUTER JOIN).
        #
        # NOTE: django will still need to make select calls to ensure there are no associated PackageInstances
        pruneable_package_ids = models.Package.objects.filter(
            packageinstance__id__isnull=True).values_list('id', flat=True)
        total_packages_pruned = 0
        for id in pruneable_package_ids:
            package = models.Package.objects.only('package_name', 'architecture', 'version').get(pk=id)
            self.logger.debug('Pruning package (%s,%s,%s)',
                         package.package_name,
                         package.architecture,
                         package.version)
            if not dry_run:
                package.delete()
            total_packages_pruned += 1
        
        
        # log and return pruning summary
        self.logger.info('Total actions pruned: %d', total_actions_pruned)
        self.logger.info('Total instances pruned: %d', total_instances_pruned)
        self.logger.info('Total packages pruned: %d', total_packages_pruned)
        return (total_instances_pruned, total_packages_pruned, total_actions_pruned)
            
    
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
            compressed_filename = tmp_filename + constants.GZIP_EXTENSION
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
                    if get_python_version() >= 2.7:
                        gzip_params['mtime'] = 0 
                    
                    gzip_fh = gzip.GzipFile(**gzip_params)
                    tmp_fh.seek(0)
                    shutil.copyfileobj(fsrc=tmp_fh, fdst=gzip_fh)
                    gzip_fh.close()
                    compressed_file_size = compressed_fh.tell()

                    # for python v2.6 and earlier, we need to manually set the mtime field to
                    # zero.  This starts at position 4 of the file (see RFC 1952)                    
                    if get_python_version() < 2.7:
                        compressed_fh.seek(4)
                        compressed_fh.write(struct.pack('<i',0))

                    packages_path = self._get_packages_path(distribution_name, section, architecture)
                    rel_packages_path = self._get_packages_relative_path(section, architecture)
                    tmp_fh.seek(0)
                    cache.set( packages_path, tmp_fh.read() )
                    compressed_fh.seek(0)
                    cache.set( packages_path + constants.GZIP_EXTENSION, 
                               compressed_fh.read(compressed_file_size) )
                    
                    # hash the package list for each hash function
                    for type in hash_types:
                        release_hashes[type].append(
                            ' {0} {1} {2}'.format(hash_file_by_fh(self._get_hashfunc(type), tmp_fh), 
                                                  tmp_file_size, 
                                                  rel_packages_path))
                        release_hashes[type].append(
                            ' {0} {1} {2}'.format(hash_file_by_fh(self._get_hashfunc(type), compressed_fh), 
                                                  compressed_file_size, 
                                                  rel_packages_path + constants.GZIP_EXTENSION))

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
        gpg_signer = GPGSigner()
        release_signature = gpg_signer.sign_data(release_contents)
        
        releases_path = self._get_releases_path(distribution)
        cache.set(releases_path, (release_contents, release_signature) )
        
        return (release_contents, release_signature)


    def _clear_cache(self, distribution_name):
        distribution = models.Distribution.objects.get(name=distribution_name)
        sections = models.Section.objects.filter(distribution=distribution).values_list('name', flat=True)
        architectures = distribution.get_architecture_list()
        
        for section in sections:
            for architecture in architectures:
                packages_path = self._get_packages_path(distribution_name, section, architecture)
                cache.delete_many([ packages_path, packages_path + constants.GZIP_EXTENSION ])
        
        releases_path = self._get_releases_path(distribution_name)
        cache.delete_many([releases_path, releases_path + constants.GPG_EXTENSION])


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

    @staticmethod
    def _find_pruneable_instances(instances, package_prune_limit):
        """
        Returns a list of instances IDs for pruning
        """

        # Comparison function used to sort instances by Debian package version
        def _compare_instances_by_version(a, b):
            return version_compare(a.package.version, b.package.version)

        pruneable_instance_ids = []
        sorted_by_version = sorted(instances, 
                                   cmp=_compare_instances_by_version, 
                                   reverse=True)
        
        # prune all instances IDs beyond the prune limit in the sorted list
        # of instances
        for prunable_instance in sorted_by_version[package_prune_limit:]:
            pruneable_instance_ids.append(prunable_instance.id)
            
        return pruneable_instance_ids
