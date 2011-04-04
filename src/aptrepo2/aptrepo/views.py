from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from aptrepo2.settings import APTREPO_FILESTORE_ROOT
import models
import os
import hashlib
import re
import string
import subprocess

fs = FileSystemStorage(location=APTREPO_FILESTORE_ROOT)
HASH_BLOCK_MULTIPLE = 128

class AptRepoException(Exception):
    """ Exceptions for the apt repo """
    
    message = "(Unknown error)"
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return repr(self.message)
    

def _verify_debian(deb_file):
    """ Verifies that it is a valid Debian file """
    (_, ext) = os.path.splitext(deb_file.name)
    if ext != '.deb':
        raise AptRepoException('Invalid extension: {0}'.format(ext))
    
    
def _get_debian_control_data(deb_filename):
    """ Retrieve the field name """
    
    # retrieve the control information
    dpkg_cmd = 'dpkg-deb --info {0} control'.format(deb_filename)
    dpkg_proc = subprocess.Popen(args=['dpkg-deb', '--info', deb_filename, 'control'],
                                 stdout=subprocess.PIPE)
    dpkg_proc.wait()
    if dpkg_proc.returncode != 0:
        raise AptRepoException("Command failed: " + dpkg_cmd)
    control_data = dpkg_proc.stdout.readlines()
    
    # convert the control data to a dictionary
    control = {}
    for line in control_data:
        if not re.match('^\s', line):
            (k,v) = string.split(line, ':')
            control[k.strip()] = v.strip()
    return control
    
    
def _hash_digest_file(hashfunc, filename):
    """
    Returns a hexadecimal hash digest for a file using a hashlib algorithm
    """
    with open(filename, 'rb') as fh:
        for chunk in iter(lambda: fh.read(HASH_BLOCK_MULTIPLE * hashfunc.block_size), ''):
            hashfunc.update(chunk)
        
    return hashfunc.hexdigest()

def upload_file(request):
    
    """ handles uploading a file """
    try:
        if request.method != 'POST':
            raise AptRepoException('Invalid HTTP method')
            
        uploaded_file = request.FILES['attachment']
        _verify_debian(uploaded_file)
        
        fs.delete(uploaded_file.name)
        new_file_path = fs.save(name=uploaded_file.name, content=uploaded_file)
        new_file_path = fs.path(new_file_path)
        package = models.Package(filepath=new_file_path)
        
        # extract control file information
        control = _get_debian_control_data(new_file_path)
        package.package_name = control['Package']
        package.architecture = control['Architecture']
        package.version = control['Version']
        
        # compute hashes
        package.hash_md5 = _hash_digest_file(hashlib.md5(), new_file_path)
        package.hash_sha1 = _hash_digest_file(hashlib.sha1(), new_file_path)
        package.hash_sha256 = _hash_digest_file(hashlib.sha256(), new_file_path)

        # store result and redirect to success page        
        package.save() 
        return HttpResponseRedirect(reverse('aptrepo.views.success'))
    
    except Exception as e:
        return HttpResponse(content=e.__str__(), status=406)


def success(request):
    return HttpResponse("Package successfully uploaded.")
