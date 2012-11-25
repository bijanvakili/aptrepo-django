from debian_bundle import deb822
from server.aptrepo.util import AptRepoException
from base import BaseTestDataGenerator 
from django.core.serializers import base

class DebianPackageGenerator(BaseTestDataGenerator):
    
    def __init__(self, stream):
        super(DebianPackageGenerator, self).__init__(stream)
        
        # load and parse the package list
        if 'content' not in self.params:
            raise AptRepoException("No 'content' section specified in fixture")
        with open(self.params['content']['packages_filename']) as fp_packages_file:
            self.package_list = deb822.Packages.iter_paragraphs(sequence=fp_packages_file.readlines())


    def build(self):
        for package_info in self.package_list:

            self.pk_count += 1
            
            package_data = self._make_package_from_deb822(package_info)
            yield package_data
            yield self._make_instance_data(package_data)
            yield self._make_action_data(package_data)

    
    def _make_package_from_deb822(self, package_info):

        control_map = deb822.Deb822()
        if 'section' in package_info:
            control_map['Section'] = package_info['section']
        control_map['Architecture'] = package_info['architecture']
        control_map['Maintainer'] = package_info['maintainer']
        control_map['Package'] = package_info['package']
        control_map['Version'] = package_info['version']
        control_map['Description'] = package_info['description']

        return self._make_package_data(control_map, 
                                       int(package_info['size']), 
                                       package_info['MD5Sum'])        
    
def Deserializer(stream_or_string, **options):
    """
    Deserialize method which converts data from LargeDatasetGenerator using
    the standard django PythonDeserializer
    """
    return DebianPackageGenerator(stream_or_string).get_generator(**options)

class Serializer(base.Serializer):
    pass
