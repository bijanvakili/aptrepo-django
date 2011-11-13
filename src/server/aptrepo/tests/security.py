import json
import os
import tempfile
from django.conf import settings
from base import BaseAptRepoTest, skipRepoTestIfExcluded
from server.aptrepo import models

class AuthenticationTest(BaseAptRepoTest):
    """
    Ensures authentication is enforced depending on the URLs that 
    do or do not require it
    """
    
    def setUp(self):
        # initialize base class
        super(AuthenticationTest, self).setUp()
        
        # force a logout
        self.client.logout()
        
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
        self.assertContains(response, 'Invalid username or password')

        # do an invalid password through the web page
        response = self.client.post(
            self.login_url,
            { 'username': self.username, 'password': 'badpassword' }
        )
        self.assertContains(response, 'Invalid username or password')

        
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
        self.assertContains(response, 'Invalid username or password', status_code=400)
        
        # do an invalid password through the web page
        response = self.client.post(
            login_api_url,
            { 'username': self.username, 'password': 'badpassword' }
        )
        self.assertContains(response, 'Invalid username or password', status_code=400)
        
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
