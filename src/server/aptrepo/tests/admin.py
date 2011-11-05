"""
Pruning unit tests for the apt repo
"""
import fnmatch
import logging
import os
import shutil
import tempfile
from django.conf import settings
from server.aptrepo import models
from server.aptrepo.views import get_repository_controller
from base import BaseAptRepoTest, skipRepoTestIfExcluded

class PruningTest(BaseAptRepoTest):
    
    def _ensure_db_logging(self):
        # recheck debugging environment (since django reset DEBUG flags by default)
        if 'APTREPO_DEBUG' in os.environ:
            debug_params = os.environ['APTREPO_DEBUG'].lower().split()
            if 'true' in debug_params:
                settings.DEBUG = True
            if 'db' in debug_params: 
                logger = logging.getLogger('django.db.backends')
                logger.setLevel(logging.DEBUG)
                
    def _disable_db_logging(self):
        settings.DEBUG = False
        logger = logging.getLogger('django.db.backends')
        logger.setLevel(logging.INFO)
    
    def _upload_package_set(self, name, version_list, architecture='all'):
        control_map = self._make_common_debcontrol()
        control_map['Package'] = name
        control_map['Architecture'] = architecture

        for version in version_list:
            control_map['Version'] = str(version)
            pkg_filename = None        
            try:
                # create the package
                pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix=control_map['Package'])
                os.close(pkg_fh)
                self._create_package(control_map, pkg_filename)
        
                # upload the package
                self._upload_package(pkg_filename)
                
            finally:
                if pkg_filename is not None:
                    os.remove(pkg_filename)
            
    def _verify_pruned_repo(self, expected_results):
        """
        Verifies the model in the repository using an 'if and only if' matching comparison
        
        expected_results - dictionary mapping package names to list of (architecture, version) tuples
        """
        # forward check: check to ensure each instance is in the expected set
        instances = models.PackageInstance.objects.filter(section__id=self.section_id)
        for instance in instances:
            package_name = instance.package.package_name
            self.assertTrue(package_name in expected_results, 
                            'Package {0} in expected results'.format(package_name))
            self.assertTrue((instance.package.architecture, instance.package.version)
                             in expected_results[package_name],
                             "({0},{1},{2}) in expected results".format(package_name,
                                                                        instance.package.architecture,
                                                                        instance.package.version))
                
        # reverse check: check to see if each expected result is in the instances for the section
        for package_name in expected_results.keys():
            for (architecture, version) in expected_results[package_name]:
                results = models.PackageInstance.objects.filter(section__id=self.section_id,
                                                                 package__package_name=package_name,
                                                                 package__architecture=architecture,
                                                                 package__version=version)
                self.assertEqual(len(results), 1, 
                                 '({0},{1},{2}) in database'.format(package_name,architecture,version))
                
        # ensure no stale packages exist in the Packages table
        n_packages = 0
        for package in models.Package.objects.all():
            self.assertTrue(package.package_name in expected_results, "Stale package name")
            self.assertTrue((package.architecture, package.version) in expected_results[package.package_name], 
                            "Stale package version")
            self.assertTrue(os.path.exists(package.path.path), "Package file exists")
            n_packages += 1
            
        # ensure no extra package files exist
        package_root = os.path.join(settings.MEDIA_ROOT,
                                    settings.APTREPO_FILESTORE['packages_subdir'])
        for root,_,files in os.walk(package_root):
            for filename in fnmatch.filter(files, '*.deb'):
                package_rel_path = root.replace(settings.MEDIA_ROOT, '')
                packages = models.Package.objects.filter(path=os.path.join(package_rel_path, filename))
                self.assertTrue(packages.count() == 1, "Package file is actually referenced in database")
            
        # ensure the number of actions for the section meets the limit
        section = models.Section.objects.get(id=self.section_id)
        if section.action_prune_limit > 0:
            num_actions = models.Action.objects.filter(section=section).count()
            self.assertTrue(num_actions <= section.action_prune_limit, "Too many actions")
    
    def _make_tuple_list(self, architecture, version_list):
        l = []
        for version in version_list:
            l.append( (architecture, str(version)) )
            
        return l

    @skipRepoTestIfExcluded
    def test_basic_pruning(self):
        
        try:
            """
            temporarily add an architecture type to be removed later
            """
            temparch = models.Architecture.objects.create(name='temparch')
            models.Distribution.objects.get(
                name=self.distribution_name).suppported_architectures.add(temparch)
            
            """
            setup set of packages to be pruned as follows
            (default to 'all' architecture unless specified)
            
            before:
            a1-a6
            b1
            c1 - c5
            d1-d4,d7,d9-d10
            e1-e4
            f1 (architecture is 'temparch')
            """
            self._upload_package_set('a', [1,2,3,4,5,6])
            self._upload_package_set('b', [1])
            self._upload_package_set('c', [1,2,3,4,5])
            self._upload_package_set('d', [1,2,3,4,7,9,10])
            self._upload_package_set('e', [1,2,3,4])
            self._upload_package_set('f', [1], architecture=temparch.name)
            
            # remove the temporary architecture
            temparch.delete()
            
            # prune the packages
            repo = get_repository_controller()
            self._ensure_db_logging()
            repo.prune_sections([self.section_id])
            self._disable_db_logging()
            
            """
            verify that this is the state of the repo after pruning:
            
            a2-a6
            b1
            c1-c5
            d3,d4,d7,d9,10
            e1-e4
            """
            
            pruned_state = {}
            pruned_state['a'] = self._make_tuple_list('all', [2,3,4,5,6])
            pruned_state['b'] = self._make_tuple_list('all', [1])
            pruned_state['c'] = self._make_tuple_list('all', [1,2,3,4,5])
            pruned_state['d'] = self._make_tuple_list('all', [3,4,7,9,10])
            pruned_state['e'] = self._make_tuple_list('all', [1,2,3,4])
            
            self._verify_pruned_repo(pruned_state)
        finally:
            self._disable_db_logging()
        
    @skipRepoTestIfExcluded
    def test_versionpruning_by_architecture(self):
        
        try:
            """
            setup a list of packages to be pruned as follows
            
            before:
            a:
                i386: a1-a5
                amd64: a6-a10
            b:
                i386: a1-a10
                amd64: a6-a10
            """
            self._upload_package_set('a', [1,2,3,4,5], 'i386')
            self._upload_package_set('a', [6,7,8,9,10], 'amd64')
            self._upload_package_set('b', [1,2,3,4,5,6,7,8,9,10], 'i386')
            self._upload_package_set('b', [6,7,8,9,10], 'amd64')
            
            # prune the packages
            repo = get_repository_controller()
            self._ensure_db_logging()
            repo.prune_sections([self.section_id])
            self._disable_db_logging()
            
            """
            after:
            a:
                i386: a1-a5
                amd64: a6-a10
            b:
                i386: a6-a10
                amd64: a6-a10
            """
            pruned_state = {}
            pruned_state['a'] = self._make_tuple_list('i386', [1,2,3,4,5]) + \
                self._make_tuple_list('amd64', [6,7,8,9,10])
            pruned_state['b'] = self._make_tuple_list('i386', [6,7,8,9,10]) + \
                self._make_tuple_list('amd64', [6,7,8,9,10])
            
            self._verify_pruned_repo(pruned_state)
        finally:
            self._disable_db_logging()


class ImportTest(BaseAptRepoTest):
    
    @skipRepoTestIfExcluded
    def test_flat_directory(self):
        """
        - create temporary folder
        - create 3 Debian packages within the temporary folder
        - import all packages
        
        - verify repo metadata
        - use the REST API to ensure all packages were loaded  
        """
        
        temp_import_dir = None
        try:
            temp_import_dir = tempfile.mkdtemp()
            
            # create 3 Debian packages for import
            control = self._make_common_debcontrol()
            package_names = set()
            for i in xrange(3):
                control['Package'] = 'imp-' + chr(ord('a') + i)
                package_names.add(control['Package'])
                self._create_package(control, 
                                     os.path.join(temp_import_dir, self._make_valid_deb_filename(control)))

            # create a subdirectory with a single package which should be ignored
            subdir_name = 'subdir'
            os.mkdir(os.path.join(temp_import_dir, subdir_name))
            control['Package'] = 'imp-toignore'
            self._create_package(control, 
                                 os.path.join(temp_import_dir,
                                              subdir_name, 
                                              self._make_valid_deb_filename(control)))

            # import the flat directory only
            repository = get_repository_controller()
            repository.import_dir(section_id=self.section_id, 
                                  dir_path=temp_import_dir, recursive=False)

            # verify the repository            
            self._verify_repo_metadata()
            for package_name in package_names:
                self.assertTrue(
                    self._exists_package(package_name, control['Version'], 
                                         control['Architecture']))

            # check the results
            self._check_import_results(package_names, control['Version'], 
                                       control['Architecture'])
        finally:
            if temp_import_dir is not None:
                shutil.rmtree(temp_import_dir)

    
    @skipRepoTestIfExcluded
    def test_recursive_directories(self):
        """
        - create temporary folder
        - create 3 directories with 3 Debian packages each within the temporary folder
        - import all packages
        
        - verify repo metadata
        - use the REST API to ensure all packages were loaded  
        """
        temp_import_dir = None
        try:
            temp_import_dir = tempfile.mkdtemp()
            
            # create 3 Debian packages for import
            control = self._make_common_debcontrol()
            package_names = set()
            for i in xrange(3):
                subdir_name = 'subdir' + str(i + 1)
                os.mkdir(os.path.join(temp_import_dir, subdir_name))
                for j in xrange(3):
                    control['Package'] = 'imp-' + chr(ord('a') + i*3 + j)
                    package_names.add(control['Package'])
                    self._create_package(control, 
                        os.path.join(temp_import_dir, subdir_name, 
                                     self._make_valid_deb_filename(control)))

            # import the flat directory        
            repository = get_repository_controller()
            repository.import_dir(section_id=self.section_id, 
                                  dir_path=temp_import_dir, recursive=True)

            # check the results
            self._check_import_results(package_names, control['Version'], 
                                       control['Architecture'])
        finally:
            if temp_import_dir is not None:
                shutil.rmtree(temp_import_dir)
    
    def _make_valid_deb_filename(self, control):
        return '{0}_{1}_{2}.deb'.format(control['Package'], control['Version'], control['Architecture'])

    def _check_import_results(self, package_names, version, architecture):
        """
        Verifies that a set of package names are in the repo
        """
        self._verify_repo_metadata()
        
        # ensure the packages were actually imported
        for package_name in package_names:
            self.assertTrue(self._exists_package(package_name, version, architecture))

        # ensure there are no packages in the repo that were not meant to be imported
        instance_list = self._download_json_object(self._ROOT_APIDIR + '/sections/' + 
                                                  str(self.section_id) + '/package-instances/')
        for instance in instance_list:
            self.assertTrue(instance['package']['package_name'] in package_names)
