"""
Unit tests for apt repo
"""

from django.test import TestCase, Client
import os
import tempfile

from aptrepo2.settings import TEST_DATA_ROOT, APTREPO_FILESTORE_ROOT

class PackageUploadTest(TestCase):

    def setUp(self):
        # remove all previously uploaded Debian files
        os.system('rm {0}/*.deb'.format(APTREPO_FILESTORE_ROOT))

    def _create_package(self, src_root_dir, pkg_filename):
        ret = os.system('dpkg --build {0} {1}'.format(src_root_dir, pkg_filename))
        return (ret >> 16) == 0
    
    def test_package_upload(self):
        """ test a simple package upload """
        pkg_filename = None
        try:
            c = Client()
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='mypackage')
            os.close(pkg_fh)
            self.assertTrue(self._create_package(
                os.path.join(TEST_DATA_ROOT,'test-package'), 
                pkg_filename))

            # upload the file            
            with open(pkg_filename) as f:
                response = c.post('/aptrepo/package/upload', {'attachment' : f})
                print response.content
                self.failUnlessEqual(response.status_code, 302)
                
        finally:
            if pkg_filename is not None:
                os.remove(pkg_filename)
