from debian_bundle import deb822
from server.aptrepo.util import AptRepoException
from base import BaseTestDataGenerator
from django.core.serializers import base

class GroupedDatasetGenerator(BaseTestDataGenerator):
    """
    Internal generator class to procedurally produce a objects that can be
    read by the PythonDeserializer
    """
    def __init__(self, stream):
        super(GroupedDatasetGenerator, self).__init__(stream)
        if 'packages' not in self.params:
            raise AptRepoException("No 'packages' specified in fixture")
    
    def build(self):
        """
        Creates an iterator for traversing the package tree
        """
        for package_dict in self.params['packages']:
            for package_name, versions in package_dict.iteritems():
                for version_dict in versions:
                    for version, architectures in version_dict.iteritems():
                        for architecture in architectures:
                            self.pk_count += 1
                            control_map = self._make_control_map(package_name, 
                                                                 version, 
                                                                 architecture)
                            package_data = self._make_package_data(control_map)
                            yield package_data
                            yield self._make_instance_data(package_data)
                            yield self._make_action_data(package_data)
                            

    def _make_control_map(self, package_name, version, architecture):
        package_defaults = self.params['defaults']['package']
        
        control_map = deb822.Deb822()
        control_map['Package'] = package_name
        control_map['Version'] = version
        control_map['Architecture'] = architecture
        
        control_map['Section'] = package_defaults['section']
        control_map['Priority'] = package_defaults['priority']
        control_map['Maintainer'] = 'Test User <test@test.com>'
        control_map['Description'] = control_map['Package']
        return control_map


def Deserializer(stream_or_string, **options):
    return GroupedDatasetGenerator(stream_or_string).get_generator(**options)

class Serializer(base.Serializer):
    pass
