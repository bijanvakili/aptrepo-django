#!/usr/bin/env python

import json
import poster.encode
import poster.streaminghttp
import urllib
import urllib2


"""
Apt Repository API library

This package provides a sample REST API client to the Apt repository using
the JSON content type. 
"""

class AptRepoClientException:
    """ 
    API client exception class 
    """
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return self.message


class HTTPDeleteRequest(urllib2.Request):
    """
    Derived class for making HTTP DELETE requests
    """
    def get_method(self):
        return 'DELETE'    

    
class AptRepoClient:
    """
    Client REST API
    """

    _DEFAULT_API_URL = 'http://127.0.0.1:8000/aptrepo/api'
    _DISTS_PREFIX = 'dists/'
    _ACTIONS_PREFIX = 'actions/'
    _PACKAGES_SUFFIX = '/packages'
    
    def __init__(self, url=None, username=None, password=None, timeout=None):
        """
        Constructor to set up an API connection
        
        url -- URL to Apt repo server (defaults to http://127.0.0.1:8000/aptrepo/api)
        username -- Optional username for authentication
        password -- Optional password for authentication
        """
        
        if url is None:
            self.urlprefix = self._DEFAULT_API_URL
        else:
            self.urlprefix = url
        
        # setup password authentication for REST connections
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, self.url, username, password)
        handlers = []
        handlers.append(urllib2.HTTPBasicAuthHandler(password_manager))
        handlers.append(poster.streaminghttp.get_handlers())
        self.urlclient = urllib2.build_opener(handlers)
        self.timeout = None
    

    def get_package_metadata(self, id=None, name=None, version=None, architecture=None):
        """
        Retrieves the metadata for a Debian package
        
        id -- Integer unique identifier for the Debian package
        OR
        name -- Debian package name (Package)
        version -- Package version string
        architecture -- Architecture string for package (i386, amd64, all, etc.)
        """
        url = self._package_url(id, name, version, architecture)
        return self._get_request(url)

    
    def get_distribution_list(self):
        """
        Retrieves the list of distributions
        """
        return self._get_request(self._DISTS_PREFIX)        
    
    
    def get_distribution_metadata(self, id=None, name=None):
        """
        Retrieves the metadata for a distribution
    
        id -- Integer unique identifier for the distribution
        OR 
        distribution -- Distribution name
        """
        url = self._DISTS_PREFIX
        if id:
            url = url + '?' + urllib.urlencode({'distribution_id':id})
        elif name:
            url = url + '/' + name
        else:
            raise AptRepoClientException(
                'Must specify either \'id\' or \'name\' for distribution')
            
        return self._get_request(url)
    
    
    def get_section_data(self, id=None, distribution_name=None, section_name=None):
        """
        Retrieves the metadata for a repository section
        
        id -- Integer unique identifier for the section
        OR        
        distribution_name -- Distribution name
        section_name -- Section name
        """
        return self._get_request(self._section_url(id, distribution_name, section_name))


    def list_section_packages(self, id=None, distribution_name=None, section_name=None):
        """
        Retrieves the list of packages for a repository section
        
        id -- Integer unique identifier for the section
        OR        
        distribution_name -- Distribution name
        section_name -- Section name
        """
        return self._get_request(self._section_url(id, distribution_name, section_name) + 
                                 self._PACKAGES_SUFFIX)
        
        
    def upload_package(self, id=None, distribution_name=None, section_name=None, filename=None, fileobj=None):
        
        data = {}
        try:
            url = self._section_url(id, distribution_name, section_name) + self._PACKAGES_SUFFIX
            if fileobj:
                data['file'] = fileobj
            else:
                data['file'] = open(filename, 'rb')
                
            return self._post_request(url, data)
        
        finally:
            if not fileobj:
                data['file'].close()
                
    def copy_package(self, src_id, dest_distribution_name, dest_section_name):
        url = self._section_url(distribution=dest_distribution_name, 
                                section=dest_section_name) + self._PACKAGES_SUFFIX
        self._post_request(url, {'id': src_id})
        
        
    def delete_package_instance(self, instance_id):
        """
        Deletes a package instance from a section
        """
        url = self._DISTS_PREFIX + '/?' + \
            urllib.urlencode({'instance_id':instance_id})
        self._delete_request(url)
        
    def delete_all_package_instances(self, id=None, name=None, version=None, 
                                     architecture=None):
        """
        Deletes all instances associated with a package from the repository
        """
        url = self._package_url(id, name, version, architecture)
        self._delete_request(url)
        
    def list_actions(self, **kwargs):
        """
        Retrieves a list of apt repo actions
        
        Filter parameters are as follows:
        
        distrubtion_id -- distribution
        section_id -- section 
        max -- maximum number of actions to retrieve
        """
        url = self._ACTIONS_PREFIX + '/?' + urllib.urlencode(kwargs)
        self._get_request(url)
        
    def get_action(self, id):
        """
        Retrieves detailed information for an action
        
        id -- action ID
        """
        url = self._ACTIONS_PREFIX + '/' + str(id)
        self._get_request(url)
            
    def _package_url(self, id=None, name=None, version=None, architecture=None):
        """
        Constructs an URL for a package
        
        id -- Integer unique identifier for the Debian package
        OR
        name -- Debian package name (Package)
        version -- Package version string
        architecture -- Architecture string for package (i386, amd64, all, etc.)
        """
        url = ''
        if id:
            url = str(id)
        elif name and version and architecture:
            url = '{0}/{1}/{2}'.format(name, version, architecture)
        else:
            raise AptRepoClientException(
                'Must specify either \'id\' or \'name,version,architecture\' for package')
            
        return url    
    
    def _section_url(self, id=None, distribution_name=None, section_name=None):
        """
        Constructs an URL for a section
        
        id -- Integer unique identifier for the section
        OR        
        distribution_name -- Distribution name
        section_name -- Section name
        """
        url = self._DISTS_PREFIX
        if id:
            url = url + '?' + urllib.urlencode({'section_id':id})
        elif distribution_name and section_name:
            url = url + '{0}/{1}'.format(distribution_name, section_name)
        else:
            raise AptRepoClientException(
                'Must specify either \'id\' or \'distribution_name,section_name\' for section')

        return url


    def _get_request(self, url):
        """
        Internal method for GET requests
        """
        page = self.urlclient.open(url='{0}/{1}'.format(self.urlprefix, url), 
                                   timeout=self.timeout)
        return json.load(page)
    
    def _post_request(self, url, data):
        """
        Internal method for POST requests
        """
        datagen, headers = poster.encode.multipart_encode(data)
        request = urllib2.Request(url='{0}/{1}'.format(self.urlprefix, url),
                                  datagen, headers)
        
        page = self.urlclient.open(url=request, timeout=self.timeout)
        return json.load(page)

    def _delete_request(self, url):
        """
        Internal method for DELETE requests
        """
        request = HTTPDeleteRequest(url='{0}/{1}'.format(self.urlprefix, url))
        self.urlclient.open(url=request, timeout=self.timeout)
