from debian_bundle import deb822
from server.aptrepo import models
from server.aptrepo.util import AptRepoException
from base import BaseTestDataGenerator
from django.core.serializers import base

class LargeDatasetGenerator(BaseTestDataGenerator):
    """
    Internal generator class to procedurally produce a objects that can be
    read by the PythonDeserializer
    """
    
    def __init__(self, stream):
        super(LargeDatasetGenerator, self).__init__(stream)
        if 'dataset' not in self.params:
            raise AptRepoException("No 'dataset' specified in fixture")

        # preload natural keys
        self.default_architecture = models.Architecture.objects.get(
            pk=self.params['defaults']['package']['architecture']).name
        self.size = self.params['dataset']['size']

    def build(self):
        for i in xrange(self.size):
            self.pk_count = i
            package_data = self._make_next_package_from_index(i)
            yield package_data
            yield self._make_instance_data(package_data)
            yield self._make_action_data(package_data)

    def _make_next_package_from_index(self, index):
        package_defaults = self.params['defaults']['package']
        
        control_map = deb822.Deb822()
        control_map['Section'] = package_defaults['section']
        control_map['Priority'] = package_defaults['priority']
        control_map['Architecture'] = self.default_architecture
        control_map['Maintainer'] = 'Test User <test@test.com>'
        control_map['Package'] = self._get_package_name(index)
        control_map['Version'] = self._get_package_version(index)
        control_map['Description'] = str(index)
        return self._make_package_data(control_map) 

    def _get_package_name(self, index):
        return self.params['defaults']['package']['name-prefix'] + str(index)
    
    def _get_package_version(self, index):
        return '1.{0:03d}'.format(index)
        
        
            
def Deserializer(stream_or_string, **options):
    return LargeDatasetGenerator(stream_or_string).get_generator(**options)

class Serializer(base.Serializer):
    pass
