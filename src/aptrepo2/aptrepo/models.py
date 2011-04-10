import hashlib
import os
from django.db import models
from debian_bundle import debfile
from common import hash_file, AptRepoException

class Package(models.Model):
    """
    Unique Debian package
    """
    
    # normalized fields
    filepath = models.CharField(max_length=255, unique=True)
    
    # denormalized
    package_name = models.CharField(max_length=255, db_index=True)
    architecture = models.CharField(max_length=255)
    version = models.CharField(max_length=255, db_index=True)
    
    # all hash fields use double the size to store hexadecimal values
    hash_md5 = models.CharField(max_length=16*2)
    hash_sha1 = models.CharField(max_length=20*2)
    hash_sha256 = models.CharField(max_length=32*2)


    @staticmethod
    def load_fromfile(filepath):
        (_, ext) = os.path.splitext(filepath)
        if ext != '.deb':
            raise AptRepoException('Invalid extension: {0}'.format(ext))
        
        # extract control file information
        deb = debfile.DebFile(filepath)
        control = deb.debcontrol()
        package = Package(filepath=filepath)
        package.package_name = control['Package']
        package.architecture = control['Architecture']
        package.version = control['Version']
        
        # compute hashes
        package.hash_md5 = hash_file(hashlib.md5(), filepath)
        package.hash_sha1 = hash_file(hashlib.sha1(), filepath)
        package.hash_sha256 = hash_file(hashlib.sha256(), filepath)
        
        return package
        

class Distribution(models.Model):
    """ 
    Repo distribution (composite of sections)
    """
    name = models.CharField(max_length=255)


class Section(models.Model):
    """
    Grouping of packages
    """
    name = models.CharField(max_length=255)
    distribution = models.ForeignKey('Distribution') 
    
    
class PackageInstance(models.Model):
    """ 
    Package instance 
    """
    package = models.ForeignKey('Package')
    section = models.ForeignKey('Section')
    
    creator = models.CharField(max_length=255)
    creation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    is_deleted = models.BooleanField()


class Action(models.Model):
    """
    Loggable actions on the apt repo
    """
    ACTION_TYPE_CHOICES = (
        (0, 'upload'),
        (1, 'delete'),
        (2, 'move'),
    )

    instance = models.ForeignKey('PackageInstance')
    action = models.IntegerField(choices=ACTION_TYPE_CHOICES)
    user = models.CharField(max_length=255) 
    details = models.TextField()
    comment = models.TextField()
