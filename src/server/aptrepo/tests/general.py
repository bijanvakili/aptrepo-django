"""
General unit tests for apt repo
"""

import hashlib
import json
import os
import shutil
import tempfile
import zlib
from debian_bundle import deb822, debfile
from django.conf import settings
from server.aptrepo import models
from server.aptrepo.util.hash import hash_file_by_fh
from base import BaseAptRepoTest, skipRepoTestIfExcluded


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

                
    def _remove_package(self, package_name, version, architecture):
        """
        Removes a specified package instance
        """
        response = self.client.post(
            '/aptrepo/packages/delete', {
                'distribution' : self.distribution_name, 'section' : self.section_name,
                'name' : package_name, 'version': version, 'architecture': architecture})
        self.failUnlessEqual(response.status_code, 302)
        
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
    _PACKAGE_SUBDIR = 'XX'
    _PACKAGE_NAME_PREFIX = 'test-package'

    def setUp(self):

        # initialize base class
        super(LargeRepositoryTest, self).setUp()

        self.packages_path = '{0}{1}/{2}'.format( 
            settings.MEDIA_ROOT,
            settings.APTREPO_FILESTORE['packages_subdir'],
            self._PACKAGE_SUBDIR)
        os.mkdir(self.packages_path)

        # create pre-uploaded packages (with no Debian files though) along with associated
        # instances and upload actions
        for i in xrange(200):
            control_map = self._make_common_debcontrol()
            control_map['Package'] = self._PACKAGE_NAME_PREFIX + str(i)
            control_map['Version'] = self._make_test_version(i)
            control_map['Description'] = str(i)
            
            package = models.Package()
            package.package_name = control_map['Package']
            package.architecture = control_map['Architecture']
            package.version = control_map['Version']
            package.control = control_map.dump()

            # create an empty package file
            filename = '{0}_{1}_{2}.deb'.format( 
                package.package_name, 
                package.version, 
                package.architecture)
            package.path = '{0}/{1}'.format(self._PACKAGE_SUBDIR, filename)
            open(self.packages_path + '/' + filename, 'w').close()
            
            package.size = 100
            package.hash_md5 = 'XX' 
            package.hash_sha1 = 'XX'
            package.hash_sha256 = 'XX'
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
            
    def tearDown(self):
        if self.packages_path and  os.path.exists(self.packages_path):
            shutil.rmtree(self.packages_path)
            
        super(LargeRepositoryTest, self).tearDown()
            
    def _make_details(self, package):
        return '{0},{1},{2}'.format(package['package_name'], package['version'],
                                    package['architecture'])
        
    def _make_test_version(self, number):
        return '2.{0:03d}'.format(number)

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
                self.assertEqual(package_list[j]['version'], self._make_test_version(correct_id) )
                self.assertEqual(package_list[j]['architecture'], self._DEFAULT_ARCHITECTURE)
                
                self.assertEqual(instance_list[j]['package']['package_name'], 
                                 self._PACKAGE_NAME_PREFIX + str(correct_id))
                self.assertEqual(instance_list[j]['package']['version'], self._make_test_version(correct_id) )
                self.assertEqual(instance_list[j]['package']['architecture'], self._DEFAULT_ARCHITECTURE)
                
                self.assertEqual(action_list[j]['section']['id'], self.section_id )
                self.assertEqual(action_list[j]['user'], 'testuser')
                self.assertEqual(action_list[j]['action'], models.Action.UPLOAD)
                self.assertEqual(action_list[j]['details'], self._make_details(package_list[j]))

    def test_constraints_after_deletion(self):
        """
        Remove and test ranges        
        """
        self._remove_package(199)
        self._verify_testdata_range(190, 10, range(190,199) )
        
        self._remove_package(100)
        self._verify_testdata_range(98, 5, [98,99,101,102,103] )
        
        self._remove_package(10)
        self._verify_testdata_range(9, 5, [9,11,12,13,14] )        
        self._remove_package(0)
        self._verify_testdata_range(0, 10, [1,2,3,4,5,6,7,8,9,11] )


    def _remove_package(self, number):
        package_url = '{0}/packages/deb822/{1}/{2}/{3}'.format( 
            self._ROOT_APIDIR,
            self._PACKAGE_NAME_PREFIX + str(number),
            self._make_test_version(number),
            self._DEFAULT_ARCHITECTURE)
        self._delete(package_url)

    def _verify_testdata_range(self, offset, limit, expected_list):
        constraint_params = {'offset': offset, 'limit': limit}
        instances_url = self._ROOT_APIDIR + '/sections/' + str(self.section_id) + '/package-instances'
        instance_list = self._download_json_object(instances_url, constraint_params)
        
        self.assertLessEqual(len(instance_list), limit)
        self.assertEqual(len(instance_list), len(expected_list))
        for i in xrange(len(expected_list)):
            self.assertEqual(instance_list[i]['package']['package_name'], 
                             self._PACKAGE_NAME_PREFIX + str(expected_list[i]))
            
        actions_url = self._ROOT_APIDIR + '/sections/' + str(self.section_id) + '/actions' 
        action_list = self._download_json_object(actions_url, constraint_params)     
        self.assertLessEqual(len(action_list), limit)
        
        # disabling since it's invalid
        #self.assertEqual(len(action_list), len(expected_list))
        #for i in xrange(len(action_list)):
        #    self.assertEqual(action_list[i]['details'], self._make_details(instance_list[i]['package']))

