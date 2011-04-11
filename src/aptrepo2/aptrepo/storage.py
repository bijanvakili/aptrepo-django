from django.conf import settings
from django.core.files.storage import FileSystemStorage
import common
import hashlib
import os

class HashedStorage(FileSystemStorage):
    """
    Stores files segregated by their md5sum hash
    """
    
    def __init__(self, **kwargs):
        self.location = kwargs.get('location', settings.APTREPO_FILESTORE['location'])
        self.hash_depth = kwargs.get('hash_depth', settings.APTREPO_FILESTORE['hash_depth'])
        
    def _save(self, name, content):
        """
        Internal method to store files segregated by md5 hash
        """
        
        # compute the identify information
        hash_md5 = common.hash_file_by_fh(hashlib.md5(), content)
        prefix = hash_md5[0:self.hash_depth]
        new_storage_id = os.path.join(prefix, name)
        
        # remove the file if it already exists to replace it
        if self.exists(new_storage_id):
            self.delete(new_storage_id)

        # use the default file system storage functionality to store the file            
        return super(HashedStorage, self)._save(new_storage_id, content)
