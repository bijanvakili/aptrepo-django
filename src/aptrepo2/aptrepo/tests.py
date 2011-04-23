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
import pyme.core
from common import hash_string, hash_file_by_fh

class PackageUploadTest(TestCase):

    fixtures = ['simple_repository.json']

    def setUp(self):
        # remove all metafiles and previously uploaded Debian files
        self._clean_public_folder(settings.APTREPO_FILESTORE['metadata_subdir'])
        self._clean_public_folder(settings.APTREPO_FILESTORE['packages_subdir'])
                            
        # GPG context for signature verification
        self.gpg_context = pyme.core.Context()
        self.gpg_context.set_armor(1)
        
        # HTTP client for testing
        self.client = Client()
        
        # distribution and section name
        self.distribution_name = 'test_distribution'
        self.section_name = 'test_section'


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
            response = self.client.post(
                '/aptrepo/packages/', {
                    'file' : f, 'distribution': self.distribution_name, 'section': self.section_name})
            print response.content
            self.failUnlessEqual(response.status_code, 302)
            
    def _download_content(self, url):
        """
        Internal method to download a verify text content
        """
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        return response.content
            
    def _verify_repo_metadata(self):
        """
        Verifies all the metafiles of the repository
        """
        # retrieve and verify the Release file and signature
        root_url = '/aptrepo/public'
        root_distribution_url = root_url + '/dists/' + self.distribution_name
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
        root_public_url = '/aptrepo/public/'
        root_distribution_url = root_public_url + 'dists/{0}/'.format(distribution)
        release_content = self._download_content(root_distribution_url + 'Release')
        
        # parse the Release file to locate the component set using a Linear search
        package_metadata = None
        distribution = deb822.Release(sequence=release_content,
                                      fields=['Architectures', 'Components', 'MD5Sum'])
        packages_path = '{0}/binary-{1}/Packages'.format(section, architecture)
        for md5_entry in distribution['md5sum']:
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
        debfile_content = self._download_content(root_public_url + package_metadata['Filename'])
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
        public_key_content = self._download_content('/aptrepo/public/repo.asc.gpg')
        self.gpg_context.op_import(pyme.core.Data(string=public_key_content))
        
        # verify the signature
        release_data = pyme.core.Data(string=content)
        signature_data = pyme.core.Data(string=gpg_signature)
        self.gpg_context.op_verify(signature_data, release_data, None)
        
        result = self.gpg_context.op_verify_result()
        self.failUnlessEqual(len(result.signatures), 1)
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
