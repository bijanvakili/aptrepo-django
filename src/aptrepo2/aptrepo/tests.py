"""
Unit tests for apt repo
"""
import hashlib
import os
import shutil
import tempfile
import zlib
from django.test import TestCase, Client
from django.conf import settings
from debian_bundle import deb822, debfile
import pyme
from common import hash_string, hash_file_by_fh

class PackageUploadTest(TestCase):

    fixtures = ['simple_repository.json']

    def setUp(self):
        # remove all previously uploaded Debian files
        root_filestore_dir = os.path.join(settings.MEDIA_ROOT, 
                                          settings.APTREPO_FILESTORE['subdir'])
        filestore_contents = os.listdir(root_filestore_dir)
        for direntry in filestore_contents:
            if direntry != 'README':
                fullpath_entry = os.path.join(root_filestore_dir, direntry)
                if os.path.isdir(fullpath_entry):
                    shutil.rmtree(fullpath_entry)
                else:
                    os.remove(fullpath_entry)
                    
        # GPG context for signature verification
        self.gpg_context = pyme.core.Context
        self.gpg_context.set_armor(1)
        
        # HTTP client for testing
        self.client = Client()
        
        # distribution and section name
        self.distribution_name = 'test_distribution'
        self.section_name = 'test_section'

    def _create_package(self, src_root_dir, pkg_filename):
        """
        """
        ret = os.system('dpkg --build {0} {1}'.format(src_root_dir, pkg_filename))
        self.failUnlessEqual( ret >> 16, 0 )
    
    def _upload_package(self, pkg_filename):
        """
        Internal method to upload a package to the apt repo
        
        pkg_filename -- Package to upload
        """
        with open(pkg_filename) as f:
            response = self.client.post('/aptrepo/packages/', {'file' : f})
            print response.content
            self.failUnlessEqual(response.status_code, 302)
            
    def _download_content(self, url):
        """
        Internal method to download a verify text content
        """
        response = self.client.get('/aptrepo/public/dists/repo.asc.gpg')
        self.failUnlessEqual(response.status_code, 200)
        return response.content
            
    def _verify_repo_metadata(self):
        """
        Verifies all the metafiles of the repository
        """
        # retrieve and verify the Release file and signature
        root_distribution_url = '/aptrepo/public/dists/' + self.distribution_name
        release_content = self._download_content(root_distribution_url + '/Release')
        release_signature = self._download_content(root_distribution_url + '/Release.gpg')
        self._verify_gpg_signature(release_content, release_signature)
        
        # parse each of the Release file entries
        distribution = deb822.Release(sequence=release_content,
                                      fields=['Architectures', 'Components', 'md5sum'])
        for md5_entry in distribution['md5sum']:
            file_content = self._download_content(root_distribution_url + md5_entry['name'])
            self.failUnlessEqual(len(file_content), md5_entry['size'])
            self.failUnlessEqual(hash_string(hashlib.md5(), file_content), md5_entry['md5sum'])
    
    
    def _verify_package_download(self, distribution, section, package_name, architecture, version):
        """
        Downloads and verifies a package
        """
        
        # retrieve the Release file
        root_distribution_url = '/aptrepo/public/dists/' + distribution
        release_content = self._download_content(root_distribution_url + '/Release')
        
        # parse the Release file to locate the component set using a Linear search
        package_metadata = None
        distribution = deb822.Release(sequence=release_content,
                                      fields=['Architectures', 'Components', 'md5sum'])
        packages_path = '{1}/binary-{2}/Packages'.format(section, architecture)
        for md5_entry in distribution['md5sum']:
            if md5_entry['name'].find(packages_path) > 0:
                
                # download the Packages file and decompress if necessary
                packages_content = self._download_content(root_distribution_url + md5_entry['name'])
                if md5_entry['name'].endswith('.gz'):
                    packages_content = zlib.decompress(packages_content)
                    
                # parse and do a linear search of the packages
                package_list = deb822.Packages(sequence=packages_content)
                for package in package_list:
                    if (package['Package'], package['Architecture'], package['Version']) == (package_name, architecture, version):
                        package_metadata = package
                        break
                
                if package_metadata:
                    break
        
        # download the package and inspect it
        debfile_content = self._download_content(root_distribution_url + package_metadata['Filename'])
        pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='downloaded')
        try:
            # verify package metadata 
            os.write(pkg_fh, debfile_content)
            os.lseek(pkg_fh, 0, os.SEEK_SET)
            deb = debfile.DebFile(fileobj=pkg_fh)
            debfile_control = deb.debcontrol()
            self.failUnlessEqual(debfile_control['Package'], package_name)
            self.failUnlessEqual(debfile_control['Architecture'], architecture)
            self.failUnlessEqual(debfile_control['Version'], version)
            
            # verify package contents using the available hashes
            self.failUnlessEqual(hash_file_by_fh(pkg_fh, hashlib.md5()), package_metadata['MD5sum'])
            self.failUnlessEqual(hash_file_by_fh(pkg_fh, hashlib.sha1()), package_metadata['SHA1'])
            self.failUnlessEqual(hash_file_by_fh(pkg_fh, hashlib.sha256()), package_metadata['SHA256'])
            
        finally:
            os.close(pkg_fh)
            os.remove(pkg_filename)

                
    def _verify_gpg_signature(self, content, gpg_signature):
        """
        Verifies a GPG signature using the public key
        """
        
        # download the public key
        public_key_content = self._download_content('/aptrepo/public/dists/repo.asc.gpg')
        self.gpg_context.op_import(pyme.core.Data(string=public_key_content))
        
        # verify the signature
        release_data = pyme.core.Data(string=content)
        signature_data = pyme.core.Data(string=gpg_signature)
        self.gpg_context.op_verify(signature_data, release_data, None)
        
        result = self.gpg_context.op_verify_result()
        self.failUnlessEqual(len(result.signatures) == 1)
        self.failUnlessEqual(result.signatures[0].status, 0)
        self.failUnlessEqual(result.signatures[0].summary, 0)
    
    
    def test_single_package_upload(self):
        """ 
        Test a simple package upload 
        """
        pkg_filename = None
        try:
            pkg_fh, pkg_filename = tempfile.mkstemp(suffix='.deb', prefix='mypackage')
            os.close(pkg_fh)
            self._create_package(os.path.join(settings.TEST_DATA_ROOT,'test-package'), pkg_filename)
            self._upload_package(pkg_filename)

        finally:
            if pkg_filename is not None:
                os.remove(pkg_filename)


    def test_multiple_package_upload(self):
        """ 
        Test multiple package uploads 
        """
        num_packages = 5
        test_architecture = 'i386'
        
        # create 5 packages and upload them
        package_names = []
        for id in range(0,num_packages):
            control_map = deb822.Deb822()
            control_map['Package'] = 'test-package{0}'.format(id)
            control_map['Version'] = '1.0{0}'.format(id)
            control_map['Section'] = 'oanda'
            control_map['Priority'] = 'optional'
            control_map['Architecture'] = test_architecture
            control_map['Depends'] = 'python'
            control_map['Maintainer'] = 'Bijan Vakili <bvakili@oanda.com>'
            control_map['Description'] = 'Test package {0}'.format(id)
            
            package_names.append(control_map['Package'])
            
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

        # verify the entire repo metadata        
        self._verify_repo_metadata()
        
        # download back and verify the packages
        for id in range(0,num_packages):
            package_name = 'test-package{0}'.format(id)
            version = '1.0{0}'.format(id)
            
            self._verify_package_download(self.distribution_name, self.section_name, 
                                          package_name, test_architecture, version)
