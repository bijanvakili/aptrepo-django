import os
import json
from StringIO import StringIO
from django.conf import settings
from django.core.serializers.python import Deserializer as PythonDeserializer
from server.aptrepo.util import AptRepoException
from server.aptrepo import models

class BaseTestDataGenerator(object):
    """
    Base class for test data serialization
    """

    def __init__(self, stream_or_string):
        """
        stream - input data stream or string in JSON format
        """
        
        if isinstance(stream_or_string, basestring):
            stream = StringIO(stream_or_string)
        else:
            stream = stream_or_string
        
        
        # load the data set parameters
        self.params = json.load(stream)
        if 'defaults' not in self.params:
            raise AptRepoException("No 'defaults' specified in fixture")

        # set the private key count to zero
        self.pk_count = 0

    def build(self):
        """
        Abstract generator method for creating model data 
        """
        pass

    def get_generator(self, **options):
        """
        Deserialize method which converts data from a BaseTestDataGenerator class using
        the standard django PythonDeserializer
        """
        for obj in PythonDeserializer(self.build(), **options):
            yield obj

    def _make_package_data(self, control_map, size=0, md5sum=None):
        """
        Creates a python dict representing a Package model object
        """
        data = {'pk' : self.pk_count}
        data['model'] = 'aptrepo.package'
        fields = {'package_name': control_map['Package']}
        fields['architecture'] = control_map['Architecture']
        fields['version'] = control_map['Version']
        fields['control'] = control_map.dump()
        fields['size'] = size if size > 0 else 0
        fields['hash_md5'] = md5sum if md5sum else 'XX'
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

    def _make_instance_data(self, package_data):
        """
        Creates a python dict representing a PackageInstance model object
        """
        upload_defaults = self.params['defaults']['upload']
        data = {'pk' : self.pk_count }
        data['model'] = 'aptrepo.packageinstance'
        fields = { 'package': self.pk_count }
        fields['section'] = upload_defaults['section']
        fields['creator'] = upload_defaults['creator']
        fields['creation_date'] = upload_defaults['creation_date']
        data['fields'] = fields
        return data

    def _make_action_data(self, package_data):
        
        upload_defaults = self.params['defaults']['upload']
        data = {'pk': self.pk_count }
        data['model'] = 'aptrepo.action'
        fields = {'target_section': upload_defaults['section'] }
        fields['timestamp'] = upload_defaults['creation_date'] 
        fields['action_type'] = models.Action.UPLOAD
        
        fields['user'] = upload_defaults['creator']
        fields['comment'] = upload_defaults['comment']
        
        fields['package_name'] = package_data['fields']['package_name']
        fields['version'] = package_data['fields']['version']
        fields['architecture'] = package_data['fields']['architecture']
        data['fields'] = fields
        
        return data
