import json
import os
from StringIO import StringIO
from debian_bundle import deb822
from django.conf import settings
from django.core.serializers import base
from django.core.serializers.python import Deserializer as PythonDeserializer
from server.aptrepo.util import AptRepoException
from server.aptrepo import models

class DebianPackageGenerator(object):
    
    def __init__(self, stream):
        # load the data set parameters
        self.params = json.load(stream)
        if 'defaults' not in self.params:
            raise AptRepoException("No 'defaults' specified in fixture")
        
        # load and parse the package list
        with open(self.params['content']['packages_filename']) as fp_packages_file:
            self.package_list = deb822.Packages.iter_paragraphs(sequence=fp_packages_file.readlines())
            
        self.pk_count = 0


    def build(self):
        for package_info in self.package_list:

            self.pk_count += 1
            
            package = self._make_package(package_info)
            yield package
            instance = self._make_instance(package)
            yield instance
            yield self._next_action(package)

    
    def _make_package(self, package_info):

        control_map = deb822.Deb822()
        if 'section' in package_info:
            control_map['Section'] = package_info['section']
        control_map['Architecture'] = package_info['architecture']
        control_map['Maintainer'] = package_info['maintainer']
        control_map['Package'] = package_info['package']
        control_map['Version'] = package_info['version']
        control_map['Description'] = package_info['description']
        
        data = {'pk' : self.pk_count}
        data['model'] = 'aptrepo.package'
        fields = {'package_name': control_map['Package']}
        fields['architecture'] = control_map['Architecture']
        fields['version'] = control_map['Version']
        fields['control'] = control_map.dump()
        fields['size'] = int(package_info['size'])
        fields['hash_md5'] = package_info['MD5Sum']
        fields['hash_sha1'] = 'XX'
        fields['hash_sha256'] = 'XX'

        # create an empty package file
        filename = '{0}_{1}_{2}.deb'.format( 
            fields['package_name'], 
            fields['version'], 
            fields['architecture'])
        fields['path'] = os.path.join(
                    settings.APTREPO_FILESTORE['packages_subdir'],
                    fields['hash_md5'][:2],  
                    filename)
        data['fields'] = fields
        return data
    
    def _make_instance(self, package):
        upload_defaults = self.params['defaults']['upload']
        
        data = {'pk' : self.pk_count }
        data['model'] = 'aptrepo.packageinstance'
        fields = { 'package': package['pk'] }
        fields['section'] = upload_defaults['section']
        fields['creator'] = upload_defaults['creator']
        fields['creation_date'] = upload_defaults['creation_date']
        data['fields'] = fields
        return data

    def _next_action(self, package):
        
        upload_defaults = self.params['defaults']['upload']
        data = {'pk': self.pk_count }
        data['model'] = 'aptrepo.action'
        fields = {'target_section': upload_defaults['section'] }
        fields['timestamp'] = upload_defaults['creation_date'] 
        fields['action_type'] = models.Action.UPLOAD
        
        fields['user'] = upload_defaults['creator']
        fields['comment'] = upload_defaults['comment']
        
        fields['package_name'] = package['fields']['package_name']
        fields['version'] = package['fields']['version']
        fields['architecture'] = package['fields']['architecture']
        data['fields'] = fields
        
        return data
        

def Deserializer(stream_or_string, **options):
    """
    Deserialize method which converts data from LargeDatasetGenerator using
    the standard django PythonDeserializer
    """
    if isinstance(stream_or_string, basestring):
        stream = StringIO(stream_or_string)
    else:
        stream = stream_or_string
        
    for obj in PythonDeserializer(DebianPackageGenerator(stream).build(), **options):
        yield obj


class Serializer(base.Serializer):
    """
    Not implemented
    """
    pass
