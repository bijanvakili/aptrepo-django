from django.db import models

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
    hash_md5 = models.CharField(max_length=16)
    hash_sha1 = models.CharField(max_length=20)
    hash_sha256 = models.CharField(max_length=32)


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
