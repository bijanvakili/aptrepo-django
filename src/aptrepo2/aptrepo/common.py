# constants
HASH_BLOCK_MULTIPLE = 128

class AptRepoException(Exception):
    """ Exceptions for the apt repo """
    
    message = "(Unknown error)"
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return repr(self.message)


def hash_file(hashfunc, filename):
    """
    Returns a hexadecimal hash digest for a file using a hashlib algorithm
    """
    with open(filename, 'rb') as fh:
        for chunk in iter(lambda: fh.read(HASH_BLOCK_MULTIPLE * hashfunc.block_size), ''):
            hashfunc.update(chunk)
        
    return hashfunc.hexdigest()
