import os
from django.db import models


def uniquefile_upload_path(instance, filename):
    """
    Simple method to just store the filename
    """
    return filename

class UniqueFile(models.Model):
    """
    Unique file
    
    NOTE: All hash fields use double the size to store hexadecimal values
    """
    path = models.FileField(upload_to=uniquefile_upload_path, max_length=255, db_index=True)
    size = models.IntegerField(default=0)
    hash_md5 = models.CharField(max_length=16*2, db_index=True)
    hash_sha1 = models.CharField(max_length=20*2, db_index=True)
    hash_sha256 = models.CharField(max_length=32*2, db_index=True)
    
    def __unicode__(self):
        return self.path
    
    def base_filename(self):
        """ 
        Returns the base filename 
        """
        return os.path.basename(self.file.name)

class Package(UniqueFile):
    """
    Unique Debian package entity
    """
    # denormalized fields
    package_name = models.CharField(max_length=255, db_index=True)
    architecture = models.CharField(max_length=255, db_index=True)
    version = models.CharField(max_length=255, db_index=True)
    control = models.TextField()
    
    def __unicode__(self):
        return '({0}, {1}, {2})'.format(self.package_name, self.architecture, 
                                        self.version)


class DistributionManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)
    

class Distribution(models.Model):
    """ 
    Repo distribution (composite of sections)
    """

    objects = DistributionManager()
    
    _ARCHITECTURE_CHOICES = (
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
    suppported_architectures = models.CommaSeparatedIntegerField(max_length=80, 
                                                                 choices=_ARCHITECTURE_CHOICES)
    
    def __unicode__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    def get_architecture_list(self):
        architecture_indices = self.suppported_architectures.split(',')
        architectures = []
        for index in architecture_indices:
            _ , curr_architecture = self._ARCHITECTURE_CHOICES[int(index)] 
            architectures.append(curr_architecture)
        return architectures


class Section(models.Model):
    """
    Grouping of packages
    """
    name = models.CharField(max_length=255, db_index=True)
    distribution = models.ForeignKey('Distribution', db_index=True)
    description = models.TextField()

    def __unicode__(self):
        return '{0}:{1}'.format(self.distribution.name, self.name)

    
class PackageInstance(models.Model):
    """ 
    Package instance 
    """
    package = models.ForeignKey('Package')
    section = models.ForeignKey('Section')    
    creator = models.CharField(max_length=255)
    creation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    is_deleted = models.BooleanField()
    
    def __unicode__(self):
        return '{0} - {1}'.format(self.section, self.package)


class Action(models.Model):
    """
    Loggable actions on the apt repo
    """
    UPLOAD, DELETE, MOVE, COPY = range(4)
    
    _ACTION_TYPE_CHOICES = (
        (UPLOAD, 'upload'),
        (DELETE, 'delete'),
        (MOVE, 'move'),
        (COPY, 'copy')
    )

    instance = models.ForeignKey('PackageInstance')
    action = models.IntegerField(choices=_ACTION_TYPE_CHOICES)
    user = models.CharField(max_length=255) 
    details = models.TextField()
    comment = models.TextField()

    def __unicode__(self):
        return '({0}) {1} - {2}'.format(self.user, self.action, self.instance)

    