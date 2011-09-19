"""
Base class for aptrepo unit tests
"""
import json
import os
import shutil
import tempfile
from debian_bundle import deb822
import pyme.core
from django.test import TestCase, Client
from django.conf import settings
from server.aptrepo import models

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
