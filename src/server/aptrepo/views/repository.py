import gzip
import hashlib
import logging
import os
import shutil
import struct
import tempfile
from apt_pkg import version_compare
from django.conf import settings
from django.core.cache import cache
from django.core.files import File
from django.db.models import Q
from django.utils.translation import ugettext as _
from debian_bundle import deb822, debfile
from lockfile import FileLock
from server.aptrepo import models
from server.aptrepo.util import AptRepoException, AuthorizationException, constants
from server.aptrepo.util.hash import hash_file_by_fh, GPGSigner
from server.aptrepo.util.system import get_python_version

class Repository():
    """
    Manages the apt repository including all packages and associated metadata
    """

    _BINARYPACKAGES_PREFIX = 'binary'
    _RELEASE_FILENAME = 'Release'
    _PACKAGES_FILENAME = 'Packages'
    _DEBIAN_EXTENSION = '.deb'
    
    def __init__(self, logger=None, user=None, request=None, sys_user=False):
        """
        Constructor for Repository class
        
        logger - (optional) set custom logger, otherwise uses settings.DEFAULT_LOGGER
        user - (optional) set the current authenticated user
        request - (optional) current incoming request (which may contain an authenticated user)
        sys_user - flags whether this is a system user (defaults to False)
        """
        # set the logger
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(settings.DEFAULT_LOGGER)
            
        # store the user for authorization checks
        self.sys_user = sys_user
        if not sys_user:
            self.user = user
            if not user and request:
                self.user = request.user
        
    def get_gpg_public_key(self):
        """
        Retrieves the GPG public key as ASCII text
        """
        # attempt to retrieve the public key from the cache
        cache_key = settings.APTREPO_FILESTORE['gpg_publickey']
        gpg_public_key = cache.get(cache_key)
        if gpg_public_key:
            self.logger.debug('Retrieving GPG public key from cache')
            return gpg_public_key
        
        # return the GPG public key as ASCII text
        self.logger.debug('Loading public key from the secret key and caching')
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
            
        self.logger.debug('Retrieving Debian Packages list at: ' + packages_path)
            
        packages_data = cache.get(packages_path)
        if not packages_data:
            self._refresh_releases_data(distribution)
            packages_data = cache.get(packages_path)
            
        # in the rare case where the cache has been cleared between refreshing
        # the data and retrieving from the cache, then just return an empty
        # string
        if not packages_data:
            packages_data = ''
            
        return packages_data

    
    def get_release_data(self, distribution):
        """
        Retrieve the Debian 'Release' data
        
        distribution - name of distribution
        """
        releases_path = self._get_releases_path(distribution)
        
        self.logger.debug('Retrieving Debian Releases list at: ' + releases_path)
        
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
            raise AptRepoException(_('No section argument specified'))
        
        self._enforce_write_access(section, 'Add package')
        
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
            package_name = os.path.split(package_path)[1]
            package_size = kwargs['package_size']
        
        self.logger.info(
            'Adding package file {0} to {1}:{2} (file size={3})'.format(
                package_path, distribution.name, section.name, package_size
            )
        )
        
        # check preconditions
        ext = os.path.splitext(package_name)[1]
        if ext != self._DEBIAN_EXTENSION:
            raise AptRepoException(_('Invalid extension: {ext}'.format(ext=ext)))        

        # extract control file information for denormalized searches
        deb = debfile.DebFile(filename=package_path)
        control = deb.debcontrol()
        if self.logger.getEffectiveLevel() == logging.DEBUG:
            self.logger.debug('Package file ' + package_name + ' has control info:\n' + 
                              control.dump())
        
        if not distribution.allowed_architecture(control['Architecture']):
            raise AptRepoException(
                _('Invalid architecture for distribution ({dist}) : {arch}').format(
                    dist=distribution.name, arch=control['Architecture']))

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
                    _('({name}, {version}, {arch}) already exist with different file contents').format(
                        name=package.package_name, version=package.version, arch=package.architecture))
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
                stored_file_path = os.path.join(
                    settings.APTREPO_FILESTORE['packages_subdir'],
                    hash_prefix, 
                    '{0}_{1}_{2}{3}'.format(control['Package'], 
                                            control['Version'], 
                                            control['Architecture'],
                                            self._DEBIAN_EXTENSION))
                package.path.save(stored_file_path, package_fh) 
                
                package.save()

            except Exception:
                if package.path.name:
                    package.path.delete(package.path.name)
                raise

        # create a package instance
        self.logger.debug('Creating new package instance for ' + str(package))        
        package_instance = models.PackageInstance.objects.get_or_create(
            package=package, section=section, creator=self._get_username())[0]
        
        # record an upload action
        summary = _('{creator} added package {package}').format(creator=package_instance.creator,
                                                                package=package)
        self._record_action(models.Action.UPLOAD, 
                            section,
                            summary,
                            package=package,
                            comment=kwargs.get('comment'))
        
        # invalidate the cache and return the new instance ID
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

        self._enforce_write_access(models.Section.objects.get(id=section_id), 
                                   'Import package directory')

        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                if filename.endswith(self._DEBIAN_EXTENSION):
                    try:
                        package_path = os.path.join(dir_path, root, filename)
                        self.logger.debug('Importing ' + package_path + '...')
                         
                        if not dry_run:
                            with open(package_path, 'r') as package_file:
                                self.add_package(section_id=section_id, package_fh=package_file,
                                                 package_path=package_path, 
                                                 package_size=os.path.getsize(package_path))
                        
                        
                    except Exception as e:
                        if not ignore_errors:
                            raise
                        else:
                            self.logger.warning(e)

            if not recursive:
                del dirs[:]


    def clone_package(self, dest_section, package_id=None, instance_id=None, comment=None):
        """
        Clones a package to create another instance
        
        dest_section - destination section (model)
        
        package_id - primary key (id) of package from which to create a new instance
        OR
        instance_id - primary key (id) of an existing instance to copy
        
        Returns the new instance id
        """
        
        self._enforce_write_access(dest_section, "Clone package")
        
        # locate the target section and the source package
        src_package = None
        src_section = None
        if package_id:
            src_package=models.Package.objects.get(id=package_id)
        elif instance_id:
            src_instance = models.PackageInstance.objects.get(id=instance_id)
            src_section = src_instance.section
            if src_instance.section.id == dest_section.id:
                raise AptRepoException(_('Cannot clone into the same section'))
            src_package=src_instance.package
        
        # create the new instance
        self.logger.info('Cloning package id={0} into section={1}'.format(
            src_package.id, dest_section.id))
        package_instance = models.PackageInstance.objects.create(package=src_package,
                                                                 section=dest_section,
                                                                 creator=self._get_username())
        
        # insert action for clone
        summary = _('{creator} cloned package {package} ').format(
            creator=package_instance.creator, package=src_package)
        if src_section:
            summary = summary + _(' from {src_section} to {dest_section}').format(src_section, dest_section)
        else:
            summary = summary + _(' into {0}').format(dest_section)
        self._record_action(models.Action.COPY,
                            dest_section, 
                            summary,
                            package=src_package,
                            comment=comment)
        
        self._clear_cache(dest_section.distribution.name)
        return package_instance.id

        
    def remove_package(self, package_instance_id, comment=None):
        """
        Removes a package instance
        If there are no instances referencing the actual package, it will be removed as well
        
        package_instance_id - primary key (id) of package to remove
        """
        # remove the instance
        package_instance = models.PackageInstance.objects.get(id=package_instance_id)
        section = package_instance.section
        self._enforce_write_access(section, "Remove package")

        package_id = package_instance.package.id
        self.logger.info('Removing instance id={0} from section id={1}'.format(
            package_instance_id, section.id))
        package_instance.delete()

        # remove the referenced package if it no longer exists
        package_reference_count = models.PackageInstance.objects.filter(package__id=package_id).count()
        package = models.Package.objects.get(id=package_id)
        if package_reference_count == 0:
            self.logger.info('Removing package id={0}'.format(package.id))
            package.delete()
        
        # update for the package list for the specific section and architecture
        self._clear_cache(section.distribution.name)
        
        # insert action for removal
        summary = _('{user} removed package {package} from {section}').format(
            user=self._get_username(), package=package, section=section) 
        self._record_action(models.Action.DELETE, section, summary, comment=comment)
        
        
    def remove_all_package_instances(self, package_id, comment=None):
        """
        Removes all instances of a package
        
        package_instance_id - primary key (id) of package to remove        
        """
        instances = models.PackageInstance.objects.filter(package__id=package_id)
        for instance in instances:
            self.remove_package(package_instance_id=instance.id, comment=comment)

    
    def get_actions(self, **args):
        """
        Retrieves repository actions
        
        distribution_id - distribution from which to retrieve actions
        OR
        section_id - section from which to retrieve actions
        
        min_ts - (optional) minimum timestamp for oldest action
        max_ts - (opitonal) maximum timetsamp for newest action
        
        Returns a list of actions
        """
        
        self.logger.debug('Retrieving actions for query:\n' + str(args) + '\n')
        
        # construct query based on restrictions
        query_args = []
        if 'section_id' in args:
            query_args.append(Q(section__id=args['section_id']))
        elif 'distribution_id' in args:
            query_args.append(Q(section__distribution__id=args['distribution_id']))
            
        if 'min_ts' in args:
            query_args.append(Q(timestamp__gte=args['min_ts']))
        if 'max_ts' in args:
            query_args.append(Q(timetsamp__lte=args['max_ts']))
            
        # return the action query
        return models.Action.objects.filter(*query_args).order_by('timestamp')
        
    def get_historical_actions(self, distribution_name, section_name):
        """
        Retrieves repository actions (alternate query)
        """
        self.logger.debug('Retrieving historical actions')
        
        # construct the query based on the restrictions
        query_args = []
        if distribution_name:
            query_args.append(Q(section__distribution__name=distribution_name))
            if section_name:
                query_args.append(Q(section__name=section_name))
                self.logger.debug(' for section {0}:{1}'.format(distribution_name, section_name))
            else:
                self.logger.debug(' for distribution {0}'.format(distribution_name))
        self.logger.debug('\n')
        
        # return the action query
        return models.Action.objects.filter(*query_args).order_by('-timestamp')
    
    def prune_sections(self, section_id_list, dry_run=False, check_architecture=True):
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
        pruned_distribution_names = set()
        for section_id in section_id_list:
            
            # skip the section if it doesn't require pruning
            section = models.Section.objects.get(id=section_id)
            self._enforce_write_access(section, 'Prune section')
            num_instances_pruned = 0
            
            if check_architecture:
                # remove any invalid architectures
                valid_architectures = section.distribution.get_architecture_list()
                valid_architectures.append(models.Architecture.ARCHITECTURE_ALL)
                badarch_instances = models.PackageInstance.objects.filter(section=section)
                badarch_instances = badarch_instances.exclude(
                    package__architecture__in=valid_architectures)
                
                num_instances_pruned += len(badarch_instances)
                for instance in badarch_instances:
                    
                    # avoid logging to debug unless required since it requires a SQL join operation
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug('Pruning instance [%s,%s,%s] from %s:%s (invalid architecture)',
                                          instance.package.package_name,
                                          instance.package.architecture,
                                          instance.package.version,
                                          section.distribution.name,
                                          section.name)
                    if not dry_run:
                        instance.delete()
            
            if section.package_prune_limit > 0:
                # run bulk query for all package instances in this section and ensure their package information 
                # is available for a sequential analysis. Note that we cannot sort by version because a simple 
                # lexical comparison will not meet Debian standards.  
                instances = models.PackageInstance.objects.filter(section=section)
                instances = instances.select_related('package__package_name',
                                                     'package__architecture',
                                                     'package__version')
                instances = instances.order_by('package__package_name', 'package__architecture')
                
                oldversions_to_remove = []
                (curr_name, curr_architecture) = (None, None)
                curr_instances = []
                for instance in instances:
                    
                    # reset the count if this is a new (name,architecture) pair
                    if instance.package.package_name != curr_name or \
                        instance.package.architecture != curr_architecture:
    
                        # determine which packages to prune
                        oldversions_to_remove += Repository._find_oldversion_instances(curr_instances,
                                                                                       section.package_prune_limit)
    
                        # reset for next group                
                        curr_name = instance.package.package_name
                        curr_architecture = instance.package.architecture
                        curr_instances = []
                    
                    # add to current instance set
                    curr_instances.append(instance)
    
                # final review of pruneable old versions
                oldversions_to_remove += Repository._find_oldversion_instances(curr_instances,
                                                                               section.package_prune_limit)
                
                # remove the old versions
                num_instances_pruned += len(oldversions_to_remove)
                for instance_id in oldversions_to_remove:
                    instance = models.PackageInstance.objects.get(id=instance_id)
                    
                    # avoid logging to debug unless required since it requires a SQL join operation
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug('Pruning instance [%s,%s,%s] from %s:%s (old version)',
                                     instance.package.package_name,
                                     instance.package.architecture,
                                     instance.package.version,
                                     section.distribution.name,
                                     section.name)
                    if not dry_run:
                        instance.delete()
                        
            
            # if pruning occurred, record an action and marked distributions caches to be refresh and update
            # any aggregate measures
            summary = '{0} instances pruned from section {1}'.format(num_instances_pruned, section) 
            if num_instances_pruned > 0:
                pruned_distribution_names.add(section.distribution.name)
                total_instances_pruned += num_instances_pruned
                self._record_action(models.Action.PRUNE, section, summary)

            self.logger.info(summary)

                
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
        # NOTE: django will still need to make select calls to ensure there are no 
        # associated PackageInstances
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
        
        # clear caches
        for distribution_name in pruned_distribution_names:
            self._clear_cache(distribution_name)
        
        # log and return pruning summary
        self.logger.info('Total actions pruned: %d', total_actions_pruned)
        self.logger.info('Total instances pruned: %d', total_instances_pruned)
        self.logger.info('Total packages pruned: %d', total_packages_pruned)
        return (total_instances_pruned, total_packages_pruned, total_actions_pruned)
            
    
    def _write_package_list(self, fh, distribution, section, architecture):
        """
        Writes a package list for a repository section
        """
        
        self.logger.debug(
            'Rebuilding Debian Packages list for {0}:{1}:{2}'.format(
                distribution, section, architecture
            )
        )
        
        package_instances = models.PackageInstance.objects.filter(
            Q(section__distribution__name=distribution),
            Q(section__name=section),
            Q(package__architecture=architecture) | 
            Q(package__architecture=models.Architecture.ARCHITECTURE_ALL))
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
        
        self.logger.debug('Rebuilding Debian Releases for distribution=' + distribution_name)

        # Use an interprocess file lock for reconstructing all Release data to ensure that
        # its hashes are valid since the Packages files much be computed separately.  The lock file
        # is specific to each distribution
        lock_filename = os.path.join(settings.APTREPO_VAR_ROOT, '.releases-' + distribution_name)
        with FileLock(lock_filename):
        
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
        
        self.logger.debug('Clearing cached metadata for distribution: ' + 
                          distribution_name)
        
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
        
    def _has_write_access(self, section):
        """
        Determine write access is permitted for the specified section
        
        section -- section model object to check
        """
        # allow write access if authorization is not enforced
        if not section.enforce_authorization:
            return True
        
        # always allow write access for system uesrs 
        if self.sys_user:
            return True
        
        if self.user:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(
                    'Check autorization for user {0} in section {1}'.format(self.user.username,
                                                                            str(section))
                )
                self.logger.debug(' Belongs to groups: ' +
                    ','.join(self.user.groups.all().values_list('name', flat=True)) 
                )
            
            # check user access list
            if section.authorized_users.filter(id=self.user.id):
                return True
            
            # check group access list
            elif section.authorized_groups.filter(
                id__in=self.user.groups.all().values_list('id', flat=True)):
                return True
        
        return False
    
    def _enforce_write_access(self, section, action=None):
        """
        Ensures write access to a section or throws an AuthorizationException

        section -- section model object to check
        """
        if not self._has_write_access(section):
            message = _('Unauthorized action: {action}').format(action=action)
            if self.user:
                message = message + " (for user " + self.user.username + ")"
            raise AuthorizationException(message)

    @staticmethod
    def _find_oldversion_instances(instances, package_prune_limit):
        """
        Returns a list of instances IDs where their versions old enough to be pruned
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

    def _get_username(self):
        """
        Returns the appropriate user
        """
        if self.sys_user:
            return constants.SYSUSER_NAME
        else:
            return self.user.username

    def _record_action(self, action_type, section, summary,
                       package=None, comment=None):
        """
        Common internal method to record repository actions
        
        package_instance -- instance for which the action is applied
        action_type -- the action type (see models.Action constants)
        package -- optional package object to reference
        comment -- optional user-defined comment
        """
        action = models.Action()
        action.section = section
        action.user = self._get_username()
        action.action = action_type
        action.package = package
        action.summary = summary

        if comment:
            action.comment = comment
        self.logger.debug(
            'Recording action {0} for section {1}'.format(
                str(action), str(section)
            )
        )
        action.save()
        