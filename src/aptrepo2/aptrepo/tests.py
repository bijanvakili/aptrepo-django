"""
Unit tests for apt repo
"""

from django.test import TestCase, Client
import os
import tempfile
import shutil
from debian_bundle import deb822
from aptrepo2.settings import TEST_DATA_ROOT, APTREPO_FILESTORE_ROOT

class PackageUploadTest(TestCase):

    def setUp(self):
        # remove all previously uploaded Debian files
        os.system('rm -f {0}/*.deb'.format(APTREPO_FILESTORE_ROOT))
        self.client = Client()

    def _create_package(self, src_root_dir, pkg_filename):
        ret = os.system('dpkg --build {0} {1}'.format(src_root_dir, pkg_filename))
        self.failUnlessEqual( ret >> 16, 0 )
    
    def _upload_package(self, pkg_filename):
        with open(pkg_filename) as f:
            response = self.client.post('/aptrepo/packages/', {'file' : f})
            print response.content
            self.failUnlessEqual(response.status_code, 302)
    
    def test_singlepackage_upload(self):
        """ Test a simple package upload """
        pkg_filename = None
        try:
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='mypackage')
            os.close(pkg_fh)
            self._create_package(os.path.join(TEST_DATA_ROOT,'test-package'), pkg_filename)
            self._upload_package(pkg_filename)

        finally:
            if pkg_filename is not None:
                os.remove(pkg_filename)


    def test_multiplepackage_upload(self):
        """ Test multiple package uploads """
        num_packages = 5
        
        # create 5 packages and upload them
        for id in range(0,num_packages):
            control_map = deb822.Deb822()
            control_map['Package'] = 'test-package{0}'.format(id)
            control_map['Version'] = '1.0{0}'.format(id)
            control_map['Section'] = 'oanda'
            control_map['Priority'] = 'optional'
            control_map['Architecture'] = 'i386'
            control_map['Depends'] = 'python'
            control_map['Maintainer'] = 'Bijan Vakili <bvakili@oanda.com>'
            control_map['Description'] = 'Test package {0}'.format(id)
            
            pkg_filename = None
            pkgsrc_dir = None
            try:
                # create package source directory
                pkgsrc_dir = tempfile.mkdtemp()
                debian_dir = os.path.join(pkgsrc_dir,'DEBIAN') 
                os.mkdir(debian_dir)
                with open(os.path.join(debian_dir,'control'), 'wt') as fh_control:
                    control_map.dump(fh_control)
                
                # create the package
                pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix=control_map['Package'])
                os.close(pkg_fh)
                self._create_package(pkgsrc_dir, pkg_filename)
                
                # upload the package
                self._upload_package(pkg_filename)

            finally:
                if pkg_filename is not None:
                    os.remove(pkg_filename)
                if pkgsrc_dir is not None:
                    shutil.rmtree(pkgsrc_dir)
        
        # retrieve package list
        response = self.client.get('/aptrepo/packages/')
        print response.content
        self.failUnlessEqual(response.status_code, 200)
        
        # retrieve and verify apt repo files
        
        pass