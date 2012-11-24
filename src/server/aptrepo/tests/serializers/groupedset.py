import json
import os;
from StringIO import StringIO
from debian_bundle import deb822
from django.conf import settings
from django.core.serializers import base
from django.core.serializers.python import Deserializer as PythonDeserializer
from server.aptrepo import models
from server.aptrepo.util import AptRepoException

class GroupedDatasetGenerator(object):
    """
    Internal generator class to procedurally produce a objects that can be
    read by the PythonDeserializer
    """
    def __init__(self, stream):
        self.params = json.load(stream)
        if 'defaults' not in self.params:
            raise AptRepoException("No 'defaults' specified in fixture")
        if 'packages' not in self.params:
            raise AptRepoException("No 'packages' specified in fixture")

        # compute the total number of         
        self.package_iterator = self._traverse_package_tree()
        self.instance_iterator = self._traverse_package_tree() 
        self.action_iterator = self._traverse_package_tree()
        self.package_pk_counter = 0
        self.instance_pk_counter = 0
        self.action_pk_counter = 0
        
    def _traverse_package_tree(self):
        """
        Creates an iterator for traversing the package tree
        """
        for package_dict in self.params['packages']:
            for package_name, versions in package_dict.iteritems():
                for version_dict in versions:
                    for version, architectures in version_dict.iteritems():
                        for architecture in architectures:
                            yield { 
                                   'package_name': package_name, 
                                   'version': version, 
                                   'architecture': architecture }

    def __iter__(self):
        """
        Returns an iterator for use by external clients
        """
        return self
    
    def _next_package(self):
        curr_package = self.package_iterator.next()
        
        package_defaults = self.params['defaults']['package']
        
        control_map = deb822.Deb822()
        control_map['Package'] = curr_package['package_name']
        control_map['Version'] = curr_package['version']
        control_map['Architecture'] = curr_package['architecture']
        
        control_map['Section'] = package_defaults['section']
        control_map['Priority'] = package_defaults['priority']
        control_map['Maintainer'] = 'Test User <test@test.com>'
        control_map['Description'] = curr_package['package_name']
        
        data = {'pk' : self.package_pk_counter}
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
        fields['path'] = os.path.join(
                    settings.APTREPO_FILESTORE['packages_subdir'],
                    fields['hash_md5'][:2],  
                    filename)
        data['fields'] = fields
        
        self.package_pk_counter += 1
        return data
    
    def _next_instance(self):
        
        if self.instance_iterator.next():
            upload_defaults = self.params['defaults']['upload']
            data = {'pk' : self.instance_pk_counter }
            data['model'] = 'aptrepo.packageinstance'
            # NOTE: Assume that instances associated with packages have the same primary key
            fields = { 'package': self.instance_pk_counter }
            
            fields['section'] = upload_defaults['section']
            fields['creator'] = upload_defaults['creator']
            fields['creation_date'] = upload_defaults['creation_date']
            data['fields'] = fields
            
            self.instance_pk_counter += 1
            return data
        else:
            raise StopIteration

    def _next_action(self):
        
        curr_action = self.action_iterator.next()
        
        upload_defaults = self.params['defaults']['upload']
        data = {'pk': self.action_pk_counter }
        data['model'] = 'aptrepo.action'
        fields = {'target_section': upload_defaults['section'] }
        fields['timestamp'] = upload_defaults['creation_date'] 
        fields['action_type'] = models.Action.UPLOAD
        fields['user'] = upload_defaults['creator']
        fields['comment'] = upload_defaults['comment']
        
        fields['package_name'] = curr_action['package_name']
        fields['version'] = curr_action['version']
        fields['architecture'] = curr_action['architecture']
        
        data['fields'] = fields
        
        self.action_pk_counter += 1
        return data

    
    def next(self):
        """
        Iteration callback for adding the next object
        
        1. Add all packages
        2. Add all associated instances
        3. Add all associated actions
        """
        try:
            return self._next_package()
        except StopIteration:
            pass

        try:
            return self._next_instance()
        except StopIteration:
            pass
        
        return self._next_action()
        


def Deserializer(stream_or_string, **options):
    """
    Deserialize method which converts data from GroupedDatasetGenerator using
    the standard django PythonDeserializer
    """
    if isinstance(stream_or_string, basestring):
        stream = StringIO(stream_or_string)
    else:
        stream = stream_or_string
    for obj in PythonDeserializer(GroupedDatasetGenerator(stream), **options):
        yield obj


class Serializer(base.Serializer):
    """
    Not implemented
    """
    pass
