from debian_bundle import deb822
from django.core.serializers import base
from django.core.serializers.python import Deserializer as PythonDeserializer
import json
from server.aptrepo import models
from server.aptrepo.util import AptRepoException
from StringIO import StringIO

class LargeDatasetGenerator(object):
    """
    Internal generator class to procedurally produce a objects that can be
    read by the PythonDeserializer
    """
    
    def __init__(self, stream):
        # load the data set parameters
        self.params = json.load(stream)
        if 'defaults' not in self.params:
            raise AptRepoException("No 'defaults' specified in fixture")
        if 'dataset' not in self.params:
            raise AptRepoException("No 'dataset' specified in fixture")

        # preload natural keys
        self.default_architecture = models.Architecture.objects.get(
            pk=self.params['defaults']['package']['architecture']).name
         
        # initialize the counters
        self.size = self.params['dataset']['size']
        self.curr_package = 0
        self.curr_instance = 0
        self.curr_action = 0

    def _next_package(self):
        package_defaults = self.params['defaults']['package']
        
        control_map = deb822.Deb822()
        control_map['Section'] = package_defaults['section']
        control_map['Priority'] = package_defaults['priority']
        control_map['Architecture'] = self.default_architecture
        control_map['Maintainer'] = 'Test User <test@test.com>'
        control_map['Package'] = self._get_package_name(self.curr_package)
        control_map['Version'] = self._get_package_version(self.curr_package)
        control_map['Description'] = str(self.curr_package)
        
        data = {'pk' : self.curr_package}
        data['model'] = 'aptrepo.package'
        fields = {'package_name': control_map['Package']}
        fields['architecture'] = control_map['Architecture']
        fields['version'] = control_map['Version']
        fields['control'] = control_map.dump()
        fields['size'] = 100
        fields['hash_md5'] = 'XX' 
        fields['hash_sha1'] = 'XX'
        fields['hash_sha256'] = 'XX'

        # create an empty package file
        filename = '{0}_{1}_{2}.deb'.format( 
            fields['package_name'], 
            fields['version'], 
            fields['architecture'])
        fields['path'] = '{0}/{1}'.format(package_defaults['subdir'], filename)
        data['fields'] = fields
        
        self.curr_package += 1
        return data

    def _next_instance(self):
        
        upload_defaults = self.params['defaults']['upload']
        data = {'pk' : self.curr_instance }
        data['model'] = 'aptrepo.packageinstance'
        fields = { 'package': self.curr_instance }
        fields['section'] = upload_defaults['section']
        fields['creator'] = upload_defaults['creator']
        data['fields'] = fields
        
        self.curr_instance += 1
        return data

    def _next_action(self):
        
        upload_defaults = self.params['defaults']['upload']
        data = {'pk': self.curr_action }
        data['model'] = 'aptrepo.action'
        fields = {'target_section': upload_defaults['section'] }
        fields['action_type'] = models.Action.UPLOAD
        
        fields['user'] = upload_defaults['creator']
        fields['comment'] = upload_defaults['comment']
        
        fields['package_name'] = self._get_package_name(self.curr_action)
        fields['version'] = self._get_package_version(self.curr_action)
        fields['architecture'] = self.default_architecture
        data['fields'] = fields
        
        self.curr_action += 1
        return data
    
    def _get_package_name(self, index):
        return self.params['defaults']['package']['name-prefix'] + str(index)
    
    def _get_package_version(self, index):
        return '1.{0:03d}'.format(index)
        
    def __iter__(self):
        return self
        
    def next(self):
        """
        Iteration callback for adding the next object
        
        1. Add all packages
        2. Add all associated instances
        3. Add all associated actions
        """
        if self.curr_package < self.size:
            return self._next_package()
        elif self.curr_instance < self.size:
            return self._next_instance()
        elif self.curr_action < self.size:
            return self._next_action()
        else:
            raise StopIteration
        
            
def Deserializer(stream_or_string, **options):
    """
    Deserialize method which converts data from LargeDatasetGenerator using
    the standard django PythonDeserializer
    """
    if isinstance(stream_or_string, basestring):
        stream = StringIO(stream_or_string)
    else:
        stream = stream_or_string
    for obj in PythonDeserializer(LargeDatasetGenerator(stream), **options):
        yield obj


class Serializer(base.Serializer):
    """
    Not implemented
    """
    pass
