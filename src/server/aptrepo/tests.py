"""
Unit tests for apt repo
"""
import fnmatch
import hashlib
import json
import logging
import os
import shutil
import tempfile
import zlib
from django.test import TestCase, Client
from django.conf import settings
from debian_bundle import deb822, debfile
import pyme.core
from common import hash_string, hash_file_by_fh
import models
import repository

# global set of skipped tests
_ENV_SKIPTESTS = 'APTREPO_SKIPTESTS'
_TEST_EXCLUSIONS = ()
if _ENV_SKIPTESTS in os.environ:
    _TEST_EXCLUSIONS = set(os.environ[_ENV_SKIPTESTS].split())

def skipRepoTestIfExcluded(test_case):
    """
    Decorator to determine whether to skip a test case
    """
    def _run_test_case(self):
        if self.__class__.__name__ in _TEST_EXCLUSIONS:
            print 'Disabling test: {0}.{1}()...'.format(self.__class__.__name__, 
                                                      test_case.__name__)
        else:
            return test_case(self)

    return _run_test_case

class BaseAptRepoTest(TestCase):

    _ROOT_WEBDIR = '/aptrepo'
    _ROOT_APIDIR = '/aptrepo/api'
    _DEFAULT_ARCHITECTURE = 'i386'

    fixtures = ['simple_repository.json']

    def setUp(self):
        # distribution and section name
        self.distribution_name = 'test_distribution'
        self.section_name = 'test_section'
        section = models.Section.objects.get(name=self.section_name, 
                                             distribution__name=self.distribution_name)
        self.section_id = section.id
        
        # remove all metafiles and previously uploaded Debian files
        self._clean_public_folder(settings.APTREPO_FILESTORE['metadata_subdir'])
        self._clean_public_folder(settings.APTREPO_FILESTORE['packages_subdir'])
        cache_dir = settings.CACHES['default']['LOCATION']
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        
        # GPG context for signature verification
        self.gpg_context = pyme.core.Context()
        self.gpg_context.set_armor(1)
        
        # HTTP and REST client for testing
        self.client = Client()

    def _make_common_debcontrol(self):
        control_map = deb822.Deb822()
        control_map['Package'] = 'test-package'
        control_map['Version'] = '1.00'
        control_map['Section'] = 'oanda'
        control_map['Priority'] = 'optional'
        control_map['Architecture'] = self._DEFAULT_ARCHITECTURE
        control_map['Maintainer'] = 'Bijan Vakili <bvakili@oanda.com>'
        control_map['Description'] = 'Test package for apt repo test suite'
        
        return control_map

    def _download_content(self, url, data={}):
        """
        Internal method to download a verify text content
        """
        response = self.client.get(url, data)
        self.failUnlessEqual(response.status_code, 200)
        return response.content
    
    def _download_json_object(self, url, data={}):
        """
        Downloads and converts JSON object to a python object
        """
        content = self._download_content(url, data)
        return json.loads(content)

    def _delete(self, url):
        """
        Runs an HTTP delete operation
        """
        response = self.client.delete(url)
        self.failUnlessEqual(response.status_code, 204)

    def _clean_public_folder(self, subdir_name):
        """
        Removes every file in a directory except the root README
        """
        root_filestore_dir = os.path.join(settings.MEDIA_ROOT, subdir_name) 
        filestore_contents = os.listdir(root_filestore_dir)
        for direntry in filestore_contents:
            if direntry != 'README':
                fullpath_entry = os.path.join(root_filestore_dir, direntry)
                if os.path.isdir(fullpath_entry):
                    shutil.rmtree(fullpath_entry)
                else:
                    os.remove(fullpath_entry)

    def _create_package(self, control_map, pkg_filename):
        """
        Creates a Debian package
        """
        try:
            pkgsrc_dir = tempfile.mkdtemp()
            debian_dir = os.path.join(pkgsrc_dir,'DEBIAN') 
            os.mkdir(debian_dir)
            with open(os.path.join(debian_dir,'control'), 'wt') as fh_control:
                control_map.dump(fh_control)
            
            ret = os.system('dpkg --build {0} {1} >/dev/null 2>&1'.format(pkgsrc_dir, pkg_filename))
            self.failUnlessEqual( ret >> 16, 0 )
            
        finally:
            if pkgsrc_dir is not None:
                shutil.rmtree(pkgsrc_dir)
            
    
    def _upload_package(self, pkg_filename, section_name=None):
        """
        Internal method to upload a package to the apt repo
        
        pkg_filename -- Filename of package to upload
        """
        if not section_name:
            section_name = self.section_name
        
        with open(pkg_filename) as f:
            response = self.client.post(
                self._ROOT_WEBDIR + '/packages/', {
                    'file' : f, 'distribution': self.distribution_name, 'section': self.section_name})
            #print response.content
            self.failUnlessEqual(response.status_code, 302)


class SmallRepositoryTest(BaseAptRepoTest):

    def _upload_package_via_api(self, section_id, pkg_filename):
        """
        Internal method to upload a package via the API.
        Returns the new instance object (converted from JSON)
        
        section_id -- Target section to upload to
        pkg_filename -- Filename of package to upload
        """
        with open(pkg_filename) as f:
            response = self.client.post(
                self._ROOT_APIDIR + '/sections/' + str(section_id) + '/package-instances', {
                    'file' : f})
            self.failUnlessEqual(response.status_code, 200)
            return json.loads(response.content)
            
    def _verify_repo_metadata(self):
        """
        Verifies all the metafiles of the repository
        """
        # retrieve and verify the Release file and signature
        root_distribution_url = self._ROOT_WEBDIR + '/dists/' + self.distribution_name
        release_content = self._download_content(root_distribution_url + '/Release')
        release_signature = self._download_content(root_distribution_url + '/Release.gpg')
        self._verify_gpg_signature(release_content, release_signature)
        
        # parse each of the Release file entries
        distribution = deb822.Release(sequence=release_content,
                                      fields=['Architectures', 'Components', 'MD5Sum'])
        for md5_entry in distribution['MD5Sum']:
            file_content = self._download_content(root_distribution_url + '/' + md5_entry['name'])
            self.failUnlessEqual(len(file_content), int(md5_entry['size']))
            self.failUnlessEqual(hash_string(hashlib.md5(), file_content), md5_entry['md5sum'])
    
    
    def _verify_package_download(self, distribution, section, package_name, architecture, version):
        """
        Downloads and verifies a package
        """
        
        # retrieve the Release file
        root_distribution_url = self._ROOT_WEBDIR + '/dists/{0}/'.format(distribution)
        release_content = self._download_content(root_distribution_url + 'Release')
        packages_path = '{0}/binary-{1}/Packages'.format(section, architecture)
        
        # parse the Release file to locate the component set using a Linear search
        package_metadata = None
        release_data = deb822.Release(sequence=release_content,
                                      fields=['Architectures', 'Components', 'MD5Sum'])
        
        for md5_entry in release_data['md5sum']:
            if md5_entry['name'] == packages_path:
                
                # download the Packages file and decompress if necessary
                packages_content = self._download_content(root_distribution_url + md5_entry['name'])
                if md5_entry['name'].endswith('.gz'):
                    packages_content = zlib.decompress(packages_content)
                    
                # parse and do a linear search of the packages
                for package in deb822.Packages.iter_paragraphs(sequence=packages_content.splitlines()):
                    if (package['Package'], package['Architecture'], package['Version']) == (package_name, architecture, version):
                        package_metadata = package
                        break
                
                if package_metadata:
                    break
        
        self.assertTrue(package_metadata is not None)
        
        # download the package and inspect it
        debfile_content = self._download_content(self._ROOT_WEBDIR + '/' + package_metadata['Filename'])
        pkg_fd, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='downloaded')
        pkg_fh = os.fdopen(pkg_fd, 'wb')
        try:
            # verify package metadata 
            pkg_fh.write(debfile_content)
            pkg_fh.close()
            deb = debfile.DebFile(filename=pkg_filename)
            debfile_control = deb.debcontrol()
            self.failUnlessEqual(debfile_control['Package'], package_name)
            self.failUnlessEqual(debfile_control['Architecture'], architecture)
            self.failUnlessEqual(debfile_control['Version'], version)
            
            # verify package contents using the available hashes
            pkg_fh = open(pkg_filename, 'rb')
            self.failUnlessEqual(hash_file_by_fh(hashlib.md5(), pkg_fh), package_metadata['MD5sum'])
            self.failUnlessEqual(hash_file_by_fh(hashlib.sha1(), pkg_fh), package_metadata['SHA1'])
            self.failUnlessEqual(hash_file_by_fh(hashlib.sha256(), pkg_fh), package_metadata['SHA256'])
            
        finally:
            if pkg_fh:
                pkg_fh.close()
            os.remove(pkg_filename)

                
    def _verify_gpg_signature(self, content, gpg_signature):
        """
        Verifies a GPG signature using the public key
        """
        
        # download the public key
        public_key_content = self._download_content(
            '{0}/dists/{1}'.format(self._ROOT_WEBDIR, settings.APTREPO_FILESTORE['gpg_publickey']))
        self.gpg_context.op_import(pyme.core.Data(string=public_key_content))
        
        # verify the signature
        release_data = pyme.core.Data(string=content)
        signature_data = pyme.core.Data(string=gpg_signature)
        self.gpg_context.op_verify(signature_data, release_data, None)
        
        result = self.gpg_context.op_verify_result()
        self.failUnlessEqual(len(result.signatures), 1)
        self.failUnlessEqual(result.signatures[0].status, 0)
        self.failUnlessEqual(result.signatures[0].summary, 0)
    
    def _remove_package(self, package_name, version, architecture):
        """
        Removes a specified package instance
        """
        response = self.client.post(
            '/aptrepo/packages/delete', {
                'distribution' : self.distribution_name, 'section' : self.section_name,
                'name' : package_name, 'version': version, 'architecture': architecture})
        self.failUnlessEqual(response.status_code, 302)
        
    def _exists_package(self, package_name, version, architecture):
        """
        Inspects a section to determine whether a package exists
        """
        packages_url = '/aptrepo/dists/{0}/{1}/binary-{2}/Packages'.format(self.distribution_name, 
                                                                           self.section_name, 
                                                                           architecture)
        packages_content = self._download_content(packages_url)

        # do a linear search for the target package        
        for package in deb822.Packages.iter_paragraphs(sequence=packages_content.splitlines()):
            if (package['Package'], package['Architecture'], package['Version']) == (package_name, architecture, version):
                return True

        return False
        
    @skipRepoTestIfExcluded
    def test_single_package_upload(self):
        """ 
        Test a simple package upload 
        """
        pkg_filename = None
        try:
            # create the package
            control_map = self._make_common_debcontrol()
            control_map['Version'] = '1.01'
            control_map['Depends'] = 'vim'
            
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='mypackage')
            os.close(pkg_fh)
            self._create_package(control_map, pkg_filename)
            
            # test uploading the package
            self._upload_package(pkg_filename)
            self.assertTrue(self._exists_package(control_map['Package'], control_map['Version'], 
                            control_map['Architecture']))
            
            # test removing the package
            self._remove_package(control_map['Package'], control_map['Version'], 
                                 control_map['Architecture'])
            self._verify_repo_metadata()
            self.assertFalse(self._exists_package(control_map['Package'], control_map['Version'], 
                             control_map['Architecture']))

        finally:
            if pkg_filename is not None:
                os.remove(pkg_filename)


    @skipRepoTestIfExcluded
    def test_multiple_package_upload(self):
        """ 
        Test multiple package uploads 
        """
        num_packages = 5
        test_architecture = 'i386'
        
        # create 5 packages and upload them
        package_names = []
        for id in range(0,num_packages):
            control_map = self._make_common_debcontrol()
            control_map['Package'] = 'test-package{0}'.format(id)
            control_map['Version'] = '1.0{0}'.format(id)
            control_map['Architecture'] = test_architecture
            control_map['Depends'] = 'python'
            control_map['Description'] = 'Test package {0}'.format(id)
            
            package_names.append(control_map['Package'])
            
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
        
        # retrieve package list
        response = self.client.get(self._ROOT_WEBDIR + '/packages/')
        #print response.content
        self.failUnlessEqual(response.status_code, 200)

        # verify the entire repo metadata        
        self._verify_repo_metadata()
        
        # download back and verify the packages
        for id in range(0,num_packages):
            package_name = 'test-package{0}'.format(id)
            version = '1.0{0}'.format(id)
            
            self._verify_package_download(self.distribution_name, self.section_name, 
                                          package_name, test_architecture, version)

    @skipRepoTestIfExcluded
    def test_rest_api(self):
        """
        Tests the REST API
        """

        # query the empty repository
        distributions_url = self._ROOT_APIDIR + '/distributions'
        distribution_list = self._download_json_object(distributions_url)
        self.assertEqual(len(distribution_list), 1)
        self.assertEqual(self.distribution_name, distribution_list[0]['name'], 'Verify distribution list')

        test_distribution_url = distributions_url + '/' + str(distribution_list[0]['id'])
        distribution_metadata = self._download_json_object(test_distribution_url)
        self.assertIsNotNone(distribution_metadata)
        self.assertEqual(distribution_metadata['description'], 'Test Distribution')
        
        sections = self._download_json_object(test_distribution_url + '/sections')
        self.assertEqual(sections[0]['description'], 'Test Section')
        
        test_section_url = self._ROOT_APIDIR + '/sections/' + str(sections[0]['id'])
        section_data = self._download_json_object(test_section_url)
        self.assertIsNotNone(section_data)
        self.assertEqual(section_data['name'], 'test_section')
        self.assertEqual(section_data['description'], 'Test Section')
        
        packages_url = test_section_url + '/package-instances'
        package_list = self._download_json_object(packages_url)
        self.assertEqual(len(package_list), 0)
        
        # upload a single package and check the result
        pkg_filename = None
        try:
            # create the package
            control_map = self._make_common_debcontrol()
            control_map['Version'] = '1.01'
            control_map['Depends'] = 'vim'
            control_map['Description'] = 'Test package for apt repo test suite'
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='mypackage')
            os.close(pkg_fh)
            self._create_package(control_map, pkg_filename)
            
            # upload the package
            self._upload_package_via_api(section_id=sections[0]['id'], 
                                                   pkg_filename=pkg_filename)
            
        finally:
            if pkg_filename is not None:
                os.remove(pkg_filename)

        # check the metadata
        packages_url = test_section_url + '/package-instances'
        package_list = self._download_json_object(packages_url)
        self.assertEqual(len(package_list), 1)
        self._verify_repo_metadata()
        
        # remove the package
        self._delete(self._ROOT_APIDIR + '/package-instances/' + str(package_list[0]['id']))
        package_list = self._download_json_object(packages_url)
        self.assertEqual(len(package_list), 0)
        self._verify_repo_metadata()

        # check the resulting actions
        action_list = self._download_json_object(test_section_url + '/actions')
        self.assertEqual(len(action_list), 2)        


class LargeRepositoryTest(BaseAptRepoTest):

    _TOTAL_PACKAGES = 200

    def setUp(self):

        # initialize base class
        super(LargeRepositoryTest, self).setUp()

        # create pre-uploaded packages (with no Debian files though) along with associated
        # instances and upload actions
        for i in xrange(200):
            control_map = self._make_common_debcontrol()
            control_map['Package'] = 'test-package' + str(i)
            control_map['Version'] = '2.{0:03d}'.format(i)
            control_map['Description'] = str(i)
            
            package = models.Package()
            package.package_name = control_map['Package']
            package.architecture = control_map['Architecture']
            package.version = control_map['Version']
            package.control = control_map.dump()
            package.path = '/XXX'
            package.size = 100
            package.hash_md5 = 'XXX' 
            package.hash_sha1 = 'XXX'
            package.hash_sha256 = 'XXX'
            package.save()
            
            section = models.Section.objects.get(id=self.section_id)
            instance = models.PackageInstance.objects.create(package=package, section=section,
                                                             creator='testuser')
            action = models.Action()
            action.section = section
            action.action = models.Action.UPLOAD
            action.user = instance.creator
            action.comment = 'For testing'
            action.details = self._make_details(package.__dict__) 
            action.save()
            
    def _make_details(self, package):
        return '{0},{1},{2}'.format(package['package_name'], package['version'],
                                    package['architecture']) 

    @skipRepoTestIfExcluded
    def test_rest_api_constraints(self):
        
        lot_size = 10
        for i in xrange(self._TOTAL_PACKAGES / lot_size):
            constraint_params = {'offset': i * lot_size, 'limit':lot_size}
            
            # retrieve package lists
            packages_url = self._ROOT_APIDIR + '/packages'
            package_list = self._download_json_object(packages_url, constraint_params)
            
            self.assertEqual(len(package_list), lot_size)
            
            # retrieve the package instance list for that section
            instances_url = self._ROOT_APIDIR + '/sections/' + str(self.section_id) + '/package-instances'
            instance_list = self._download_json_object(instances_url, constraint_params)
            self.assertEqual(len(instance_list), lot_size)
            
            # retrieve the actions
            actions_url = self._ROOT_APIDIR + '/sections/' + str(self.section_id) + '/actions'
            action_list = self._download_json_object(actions_url, constraint_params)
            self.assertEqual(len(action_list), lot_size)  

            # check results
            for j in xrange(lot_size): 
                correct_id = i * lot_size + j
                
                self.assertEqual(package_list[j]['package_name'], 'test-package' + str(correct_id) )
                self.assertEqual(package_list[j]['version'], '2.{0:03d}'.format(correct_id) )
                self.assertEqual(package_list[j]['architecture'], self._DEFAULT_ARCHITECTURE)
                
                self.assertEqual(instance_list[j]['package']['package_name'], 'test-package' + str(correct_id))
                self.assertEqual(instance_list[j]['package']['version'], '2.{0:03d}'.format(correct_id) )
                self.assertEqual(instance_list[j]['package']['architecture'], self._DEFAULT_ARCHITECTURE)
                
                self.assertEqual(action_list[j]['section']['id'], self.section_id )
                self.assertEqual(action_list[j]['user'], 'testuser')
                self.assertEqual(action_list[j]['action'], models.Action.UPLOAD)
                self.assertEqual(action_list[j]['details'], self._make_details(package_list[j]))
        

        def _verify_testdata_range(self, offset, limit, expected_list):
            constraint_params = {'offset': offset, 'limit': limit}
            instances_url = self._ROOT_APIDIR + '/sections/' + str(self.section_id) + '/package-instances'
            instance_list = self._download_json_object(instances_url, constraint_params)
            
            self.assertLessEqual(len(instance_list), limit)
            self.assertequal(len(instance_list), len(expected_list))
            for i in xrange(len(expected_list)):
                self.assertEqual(instance_list[i]['package']['package_name'], 
                                 'test-package' + str(expected_list[i]))
                
            actions_url = self._ROOT_APIDIR + '/sections/' + str(self.section_id) + '/actions' 
            action_list = self._download_content(actions_url, constraint_params)     
            self.assertLessEqual(len(action_list), limit)
            self.assertequal(len(action_list), len(expected_list))
            for i in xrange(len(action_list)):
                self.assertEqual(action_list[i]['details'], self._make_details(instance_list[i]['package']))

        def test_constraints_after_deletion(self):

            # remove and test ranges        
            packages_url = self._ROOT_APIDIR + '/packages/'
            self._delete(packages_url + str(200))
            self._verify_testdata_range(190, 10, xrange(190,9) )
            
            self._delete(packages_url + str(100))
            self._verify_testdata_range(98, 5,[98,99,101,102,103] )
            
            self._delete(packages_url + str(10))
            self._delete(packages_url + str(0))
            self._verify_testdata_range(0, 10, [1,2,3,4,5,6,7,8,9,11] )
            self._verify_testdata_range(9, 5, [9,11,12,13,14] )


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
            setup set of packages to be pruned as follows
            (use only 'all' architecture)
            
            before:
            a1-a6
            b1
            c1 - c5
            d1-d4,d7,d9-d10
            e1-e4
            """
            self._upload_package_set('a', [1,2,3,4,5,6])
            self._upload_package_set('b', [1])
            self._upload_package_set('c', [1,2,3,4,5])
            self._upload_package_set('d', [1,2,3,4,7,9,10])
            self._upload_package_set('e', [1,2,3,4])
            
            # prune the packages
            repo = repository.Repository()
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
    def test_pruning_by_architecture(self):
        
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
            repo = repository.Repository()
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
