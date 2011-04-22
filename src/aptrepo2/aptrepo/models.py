import hashlib
import os
from django.db import models
from django.conf import settings
from debian_bundle import debfile
from common import AptRepoException, hash_file_by_fh


def _get_package_path(instance, filename):
    """
    Internal method to segregate Debian package files by md5 hash
    """
    hash_prefix = instance.hash_md5[0:settings.APTREPO_FILESTORE['hash_depth']]
    return os.path.join(settings.APTREPO_FILESTORE['packages_subdir'], hash_prefix, filename)


class UniqueFile(models.Model):
    """
    Unique file
    
    NOTE: All hash fields use double the size to store hexadecimal values
    """
    path = models.FileField(max_length=255, db_index=True)
    size = models.IntegerField()
    hash_md5 = models.CharField(max_length=16*2, db_index=True)
    hash_sha1 = models.CharField(max_length=20*2, db_index=True)
    hash_sha256 = models.CharField(max_length=32*2, db_index=True)
    

class Package(models.Model):
    """
    Unique Debian package entity
    """
    file = models.ForeignKey('UniqueFile', db_index=True)
    
    # denormalized fields
    package_name = models.CharField(max_length=255, db_index=True)
    architecture = models.CharField(max_length=255, db_index=True)
    version = models.CharField(max_length=255, db_index=True)
    
    
    def base_filename(self):
        """ 
        Returns the base filename for a Package file 
        """
        return os.path.basename(self.file.name)


    @staticmethod
    def save_from_file(package_file):
        """
        Creates and stores a Package instance from an uploaded package file
        """
        
        # check the file extension
        (_, ext) = os.path.splitext(package_file.name)
        if ext != '.deb':
            raise AptRepoException('Invalid extension: {0}'.format(ext))

        try:
            # compute hashes
            package = Package()
            package.hash_md5 = hash_file_by_fh(hashlib.md5(), package_file)
            package.hash_sha1 = hash_file_by_fh(hashlib.sha1(), package_file)
            package.hash_sha256 = hash_file_by_fh(hashlib.sha256(), package_file)
            
            # store the file since we need to use standard python file handles
            package.file.save(package_file.name, package_file)
            
            # extract control file information
            deb = debfile.DebFile(package.file.path)
            control = deb.debcontrol()
            package.package_name = control['Package']
            package.architecture = control['Architecture']
            package.version = control['Version']
            
            package.save()
            
        except Exception as e:
            if package.file.name:
                package.file.delete(package.file.name)
            raise e


class Distribution(models.Model):
    """ 
    Repo distribution (composite of sections)
    """
    
    ARCHITECTURE_CHOICES = (
        (0, 'all'),
        (1, 'solaris-i386'),
        (2, 'solaris-sparc'),
        (3, 'i386'),
        (4, 'amd64'),
    )
    
    name = models.CharField(max_length=255, unique=True) # a.k.a. 'codename'
    description = models.TextField()
    label = models.CharField(max_length=80)
    suite = models.CharField(max_length=80)
    origin = models.CharField(max_length=80)
    creation_date = models.DateTimeField(auto_now_add=True)
    suppported_architectures = models.CommaSeparatedIntegerField(max_length=80, choices=ARCHITECTURE_CHOICES)

    def get_by_natural_key(self, name):
        return self.get(name=name)

class Section(models.Model):
    """
    Grouping of packages
    """
    name = models.CharField(max_length=255, db_index=True)
    distribution = models.ForeignKey('Distribution', db_index=True)
    description = models.TextField()
    
    def get_by_natural_key(self, key):
        """
        Identifies the section by the syntax 'distribution:section'
        """
        (distribution, section) = key.split(':')
        return self.get(distribution=distribution, name=section)

    
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
