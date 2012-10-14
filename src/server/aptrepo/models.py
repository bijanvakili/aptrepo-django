import os
import re
from django.contrib.auth.models import User, Group
from django.db import models
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.utils.translation import ugettext as _
from server.aptrepo.util import AptRepoException

def nowhitespace(value):
    """
    Validation function to ensure no whitespace
    """
    if re.search('\s+', value):
        raise ValidationError(_("'{0}' contains whitespace").format(value))

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
    class Meta:
        abstract = True    
    
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
        return os.path.basename(self.path.name)

    def delete(self):
        """
        Removes the file
        """
        default_storage.delete(self.path.name)
        super(UniqueFile, self).delete()

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


class Architecture(models.Model):
    """
    Supported architecture
    """
    
    ARCHITECTURE_ALL = 'all'
    
    name = models.CharField(max_length=255, unique=True, validators=[nowhitespace])
    
    def __unicode__(self):
        return self.name


class DistributionManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)
    

class Distribution(models.Model):
    """ 
    Repo distribution (composite of sections)
    """

    objects = DistributionManager()
    
    name = models.CharField(max_length=255, unique=True, validators=[nowhitespace]) # a.k.a. 'codename'
    description = models.TextField()
    label = models.CharField(max_length=80, validators=[nowhitespace])
    suite = models.CharField(max_length=80, validators=[nowhitespace])
    origin = models.CharField(max_length=80, validators=[nowhitespace])
    creation_date = models.DateTimeField(auto_now_add=True)
    supported_architectures = models.ManyToManyField(Architecture, 
                                                     db_table='aptrepo_dist_architectures')
    
    def __unicode__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    def get_architecture_list(self):
        architectures = []
        for arch in self.supported_architectures.all():
            architectures.append(arch.name)
        return architectures

    def allowed_architecture(self, architecture):
        if architecture == Architecture.ARCHITECTURE_ALL:
            return True
        
        return architecture in self.supported_architectures.all().values_list('name', 
                                                                               flat=True)
        

class Section(models.Model):
    """
    Grouping of packages
    """
    name = models.CharField(max_length=255, db_index=True, validators=[nowhitespace])
    distribution = models.ForeignKey('Distribution', db_index=True)
    description = models.TextField()
    package_prune_limit = models.PositiveIntegerField(
        default=0, help_text=_('Maximum package versions to keep'))
    action_prune_limit = models.PositiveIntegerField(
        default=0, help_text=_('Maximum actions to keep'))
    
    enforce_authorization = models.BooleanField(
        default=False, 
        help_text=_("Check this box and click 'Save' to restrict write access for this section to the selected users and groups below<br/> " \
                    "Uncheck this box and click 'Save' to provide write access for this section to anyone (default)"))
    authorized_users = models.ManyToManyField(User, blank=True,
                                              db_table='aptrepo_authorized_users') 
    authorized_groups = models.ManyToManyField(Group, blank=True,
                                               db_table='aptrepo_authorized_groups')

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
    
    def __unicode__(self):
        return '{0} - {1}'.format(self.section, self.package)


class Action(models.Model):
    """
    Loggable actions on the apt repo
    (contains denormalized data to avoid joins and broken references upon delete)
    """
    UPLOAD, DELETE, PRUNE, COPY = range(4)
    MAX_COMMENT_LENGTH = 1024
    
    _ACTION_TYPE_CHOICES = (
        (UPLOAD, 'uploaded'),
        (DELETE, 'deleted'),
        (PRUNE, 'pruned'),
        (COPY, 'copied')
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action_type = models.IntegerField(choices=_ACTION_TYPE_CHOICES)
    user = models.CharField(max_length=255)
    comment = models.TextField(null=True, max_length=MAX_COMMENT_LENGTH)
    target_section = models.ForeignKey(Section, related_name='+', db_index=True)
    source_section = models.ForeignKey(Section, related_name='+', null=True)
    
    # denormalized fields
    package_name = models.CharField(max_length=255)
    architecture = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    
    def __unicode__(self):
        return '({0}) {1}:{2}'.format(self.timestamp, 
                                      self.user, 
                                      Action._ACTION_TYPE_CHOICES(self.action_type))

    def show_package_links(self):
        return self.action_type != Action.DELETE
