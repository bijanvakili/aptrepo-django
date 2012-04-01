import json
import os
import shutil
import tempfile
from django.conf import settings
from django.contrib.auth.models import User
from base import BaseAptRepoTest, skipRepoTestIfExcluded
from server.aptrepo import models
from server.aptrepo.views.repository import Repository
from server.aptrepo.util import AptRepoException, AuthorizationException


class AuthenticationTest(BaseAptRepoTest):
    """
    Ensures authentication is enforced depending on the URLs that 
    do or do not require it
    """
    INVALID_CREDENTIALS_EN_WEB_MSG = 'Please enter a correct username and password'
    INVALID_CREDENTIALS_EN_API_MSG = 'Invalid username or password'
    FORCE_LANGUAGE = 'en'
    
    def setUp(self):
        # initialize base class
        super(AuthenticationTest, self).setUp()
        
        # force a logout
        self.client.logout()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME]=self.FORCE_LANGUAGE
        
        # store the login URL
        self.login_url = self._ROOT_WEBDIR + '/login/'
        
    @skipRepoTestIfExcluded
    def test_auth_not_required(self):
        """
        Tests all URLs that do not require authentication to ensure they succeed
        """
        
        # test retrieving the GPG public key
        response = self.client.get(self._ROOT_WEBDIR + '/dists/' + settings.APTREPO_FILESTORE['gpg_publickey'])
        self.assertContains(response, '-----BEGIN PGP PUBLIC KEY BLOCK-----')
        
        # test listing distributions
        response = self.client.get(self._ROOT_APIDIR + '/distributions')
        self.assertContains(response, self.distribution_name)
        
        # test listing sections in distribution
        response = self.client.get(
            self._ROOT_WEBDIR + '/dists/{0}/Release'.format(self.distribution_name)
        )
        self.assertContains(response, self.distribution_name)
        distribution = models.Distribution.objects.get(name=self.distribution_name)
        response = self.client.get(
            self._ROOT_APIDIR + '/distributions/{0}/sections'.format(distribution.id)
        )
        self.assertContains(response, self.section_name)
        
        # test listing packages instances (will be empty)
        section = models.Section.objects.get(name=self.section_name)
        response = self.client.get(self._ROOT_APIDIR + '/sections/{0}'.format(section.id))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            self._ROOT_WEBDIR + '/dists/{0}/{1}/binary-i386/Packages'.format(
                self.distribution_name, self.section_name
            )
        )
        self.assertEqual(response.status_code, 200)
        
        # test listing the packages (will be empty)
        response = self.client.get(self._ROOT_WEBDIR + '/packages/')
        self.assertContains(response, 'Current package list')
        response = self.client.get(self._ROOT_APIDIR + '/packages')
        self.assertEqual(response.status_code, 200)
                
        # test listing actions (will be empty)
        response = self.client.get(self._ROOT_APIDIR + '/sections/{0}/actions'.format(section.id))       
        self.assertEqual(response.status_code, 200)
        
    @skipRepoTestIfExcluded
    def test_auth_required(self):
        """
        Tests all URLs that require authentication to ensure they all fail
        """
        
        try:
            # create an empty file (should not actually be uploaded)
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='mypackage')
            
            # test a package upload
            response = self.client.post(
                self._ROOT_WEBDIR + '/packages/', 
                {
                    'file' : pkg_fh, 'distribution': self.distribution_name, 
                    'section': self.section_name}
                )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(
                self.login_url  + '?next=' + self._ROOT_WEBDIR + '/packages/' in response['Location'],  
                'Verify redirect for package upload'
            )
            section = models.Section.objects.get(name=self.section_name)
            response = self.client.post(
                self._ROOT_APIDIR + '/sections/' + str(section.id) + '/package-instances', 
                {
                    'file' : pkg_fh
                }
            )
            self.assertEqual(response.status_code, 401)
            

            # test deleting a package
            response = self.client.post(
                self._ROOT_WEBDIR + '/packages/delete',
                {
                    'package_instance': 1
                }
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(
                self.login_url  + '?next=' + self._ROOT_WEBDIR + '/packages/delete' in response['Location'],  
                'Verify redirect for package delete'
            )

            # test deleting a package instance
            response = self.client.delete(self._ROOT_APIDIR + '/package-instances/1')
            self.assertEqual(response.status_code, 401)
            response = self.client.delete(
                self._ROOT_APIDIR + 
                '/sections/{0}/package-instances/deb822/mypackage/1.00/i386'.format(section.id)
            )
            self.assertEqual(response.status_code, 401)
        
        finally:
            if pkg_fh:
                os.close(pkg_fh)
            if pkg_filename is not None:
                os.remove(pkg_filename)

    @skipRepoTestIfExcluded
    def test_login_page(self):

        landing_page_url = self._ROOT_WEBDIR + '/packages/' 

        # do an invalid username
        response = self.client.post(
            self.login_url,
            { 'username': 'nonexistentuser', 'password': self.password }
        )
        self.assertContains(response, self.INVALID_CREDENTIALS_EN_WEB_MSG)

        # do an invalid password through the web page
        response = self.client.post(
            self.login_url,
            { 'username': self.username, 'password': 'badpassword' }
        )
        self.assertContains(response, self.INVALID_CREDENTIALS_EN_WEB_MSG)

        
        # do a valid login through the web page
        response = self.client.post(
            self.login_url,
            { 'username': self.username, 'password': self.password }
        )
        self.assertRedirects(response, expected_url=landing_page_url)
        self.assertIn(settings.SESSION_COOKIE_NAME, self.client.cookies, 'Verifying session token')
        session_key = self.client.cookies.get(settings.SESSION_COOKIE_NAME).value
        self._verify_session(session_key)

    @skipRepoTestIfExcluded
    def test_rest_login(self):
        login_api_url = self._ROOT_APIDIR + '/sessions/'
        
        # do an invalid username
        response = self.client.post(
            login_api_url,
            { 'username': 'nonexistentuser', 'password': self.password }
        )
        self.assertContains(response, self.INVALID_CREDENTIALS_EN_API_MSG, status_code=400)
        
        # do an invalid password through the web page
        response = self.client.post(
            login_api_url,
            { 'username': self.username, 'password': 'badpassword' }
        )
        self.assertContains(response, self.INVALID_CREDENTIALS_EN_API_MSG, status_code=400)
        
        # do a valid login through the web page
        response = self.client.post(
            login_api_url,
            { 'username': self.username, 'password': self.password }
        )
        self.assertEqual(response.status_code, 200)
        session_key = json.loads(response.content)
        self._verify_session(session_key)
        
        # do a logout
        response = self.client.delete(
            login_api_url + session_key
        )
        self.assertEqual(response.status_code, 204)
        self._verify_session(session_key, should_exist=False)
        
    def _verify_session(self, session_key, should_exist=True):
        session_backend = __import__(name=settings.SESSION_ENGINE, fromlist='SessionStore')
        session = session_backend.SessionStore(session_key)
        
        if should_exist:
            self.assertTrue(session.exists(session_key), 'Verify session exists in backend')
            self.assertTrue(session.get_expiry_age() > 0, 'Verify session has not expired')
        else:
            self.assertFalse(session.exists(session_key), 'Verify session does not exist')


class AuthorizationTest(BaseAptRepoTest):

    """
    Verifies authorization enforcement features based on authenticated user and their
    membership groups
    """
    
    fixtures = ['simple_repository', 'secured_repository']

    def setUp(self):    
        # initialize base class
        super(AuthorizationTest, self).setUp()
        
        # force a logout
        self.client.logout()
    
    @skipRepoTestIfExcluded
    def test_user_access(self):
        # login as testuser1 and upload a package to 'test_section'
        self.client.login(username='testuser1', password='testing')
        package_id_a = self._create_and_upload_package('a', self.section_id)
        
        # verify testuser1 can write to test_section_2
        test_section_2 = models.Section.objects.get(name='test_section_2')
        package_id_b = self._create_and_upload_package('b', test_section_2.id)
        instance_id = self._clone_package_with_auth(package_id_a, test_section_2.id)
        self._delete_package_with_auth(package_id=package_id_b)
        self._delete_package_with_auth(instance_id=instance_id)

    @skipRepoTestIfExcluded
    def test_group_access(self):
        # login as testuser2 and upload a package to 'test_section'
        self.client.login(username='testuser2', password='testing')
        package_id_a = self._create_and_upload_package('a', self.section_id)

        # verify testuser2 can write to test_section_3
        test_section_3 = models.Section.objects.get(name='test_section_3')
        package_id_b = self._create_and_upload_package('b', test_section_3.id)
        instance_id = self._clone_package_with_auth(package_id_a, test_section_3.id)
        self._delete_package_with_auth(package_id=package_id_b)
        self._delete_package_with_auth(instance_id=instance_id)
    
    @skipRepoTestIfExcluded
    def test_no_access(self):
        
        # login as testuser0 and upload a package to 'test_section'
        self.client.login(username='testuser0', password='testing')
        package_id_a = self._create_and_upload_package('a', self.section_id)

        # modify 'test_section' to enforce authorization
        # (at this point, nobody should have access)
        test_section = models.Section.objects.get(name='test_section')
        test_section.enforce_authorization=True
        test_section.save()
        
        # all of the following write commands should fail
        self._delete_package_with_auth(package_id=package_id_a, expect_auth_failure=True)
        self._create_and_upload_package('b', self.section_id, expect_auth_failure=True)
        
        # relogin as testuser2
        self.client.logout()
        self.client.login(username='testuser1', password='testing')
        
        # all of the following write commands to test_section_3 should fail
        test_section_3 = models.Section.objects.get(name='test_section_3')
        self._clone_package_with_auth(package_id_a, test_section_3.id, expect_auth_failure=True)
        self._create_and_upload_package('b', test_section_3.id, expect_auth_failure=True)
        
        # relogin as testuser3
        self.client.logout()
        self.client.login(username='testuser2', password='testing')        

        # all of the following write commands to test_section_2 should fail
        test_section_2 = models.Section.objects.get(name='test_section_2')
        self._clone_package_with_auth(package_id_a, test_section_2.id, expect_auth_failure=True)
        self._create_and_upload_package('b', test_section_2.id, expect_auth_failure=True)

    
    @skipRepoTestIfExcluded
    def test_management_commands(self):

        try:
            temp_import_dir = tempfile.mkdtemp()        
            test_section_2 = models.Section.objects.get(name='test_section_2')        

            # attempt to prune or import without authorization            
            repository = Repository()
            self.assertRaises(AuthorizationException, 
                              repository.prune_sections, 
                              section_id_list=[test_section_2.id])
            self.assertRaises(AuthorizationException, repository.import_dir, 
                              section_id=test_section_2.id, dir_path=temp_import_dir)

            # attempt to prune with an authorized user
            user = User.objects.get(username='testuser1')
            repository = Repository(user=user)
            repository.prune_sections(section_id_list=[test_section_2.id])
            repository.import_dir(section_id=test_section_2.id, dir_path=temp_import_dir)

            
            # attempt to prune with system user authorization
            repository = Repository(sys_user=True)
            repository.prune_sections(section_id_list=[test_section_2.id])
            repository.import_dir(section_id=test_section_2.id, dir_path=temp_import_dir)
            
        except AuthorizationException as e:
            self.fail(e)

        finally:
            if temp_import_dir:
                shutil.rmtree(temp_import_dir)

    def _create_and_upload_package(self, package_name, section_id, expect_auth_failure=False):
        """
        Creates an uploads a package and returns the package ID
        
        package_name - name of package to upload
        section_id - ID of section to upload package
        expect_auth_failure - Flag indicating whether to expect an authorization failure (defaults to False)
        """
        
        control_map = self._make_common_debcontrol()
        control_map['Package'] = package_name

        try:        
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix=package_name)
            os.close(pkg_fh)
            self._create_package(control_map, pkg_filename)

            with open(pkg_filename) as f:
                response = self.client.post(
                    self._ROOT_APIDIR + '/sections/' + str(section_id) + '/package-instances/', 
                    { 'file' : f, }
                )
                if expect_auth_failure:
                    self.assertNotEqual(response.status_code, 200, 'Upload should fail')
                else:
                    self.assertEqual(response.status_code, 200, 'Upload should succeed')
                    instance_info = json.loads(response.content)
                    return instance_info['package']['id']
            
        finally:
            if pkg_filename is not None:
                os.remove(pkg_filename)


    def _clone_package_with_auth(self, source_package_id, target_section_id, expect_auth_failure=False):
        """
        Clones an existing package and returns the new instance ID
        
        source_package_id - name of package to clone
        target_section_id - name of target section
        expect_auth_failure - Flag indicating whether to expect an authorization failure (defaults to False)
        """
        response = self.client.post(
            self._ROOT_APIDIR + '/sections/' + str(target_section_id) + '/package-instances/',
            {'package_id' : source_package_id} 
        )
        if expect_auth_failure:
            self.assertNotEqual(response.status_code, 200, 'Clone should fail')
        else:
            self.assertEqual(response.status_code, 200, 'Clone should succeed')
            instance_info = json.loads(response.content)
            return instance_info['id']


    def _delete_package_with_auth(self, package_id=None, instance_id=None, expect_auth_failure=False):
        """
        Deletes a package or package instance
        
        package_id - (Optional) id of package to delete
        instance_id - (Optional) id of instance to delete
        expect_auth_failure - Flag indicating whether to expect an authorization failure (defaults to False)
        """
        if package_id:
            response = self.client.delete(self._ROOT_APIDIR + '/packages/' + str(package_id))
        elif instance_id:
            response = self.client.delete(self._ROOT_APIDIR + '/package-instances/' + str(instance_id))
        else:
            raise AptRepoException('No arguments given to _delete_package_with_auth()')

        if expect_auth_failure:
            self.assertNotEqual(response.status_code, 204, 'Delete should fail')
        else:
            self.assertEqual(response.status_code, 204, 'Delete should succeed')
