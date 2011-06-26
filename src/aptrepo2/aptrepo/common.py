import sys

# constants
HASH_BLOCK_MULTIPLE = 128
GZIP_EXTENSION = '.gz'
GPG_EXTENSION = '.gpg'

class AptRepoException(Exception):
    """ 
    Exceptions for the apt repo
    """
    
    message = "(Unknown error)"
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return repr(self.message)


def hash_file_by_fh(hashfunc, fh, from_start=True):
    """
    Returns a hexadecimal hash digest for a file using a hashlib algorithm
    """
    if from_start:
        fh.seek(0)
    
    for chunk in iter(lambda: fh.read(HASH_BLOCK_MULTIPLE * hashfunc.block_size), ''):
        hashfunc.update(chunk)
        
    return hashfunc.hexdigest()

def hash_file(hashfunc, filename):
    """
    Returns a hexadecimal hash digest for a file using a hashlib algorithm
    """
    with open(filename, 'rb') as fh:
        return hash_file_by_fh(hashfunc, fh)

def hash_string(hashfunc, data_string):
    """
    Returns a hexadecimal hash digest for a string
    """
    hashfunc.update(data_string)
    return hashfunc.hexdigest()


def get_python_version():
    """
    Retrieves the python version as a float
    """
    return sys.version_info[0] + sys.version_info[1] * 0.1 + sys.version_info[2] * 0.01
