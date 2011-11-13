#!/usr/bin/env python

import json
import urllib
import httpclient


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


class AptRepoClient:
    """
    Client REST API
    """

    _DEFAULT_API_URL = 'http://127.0.0.1:8000/aptrepo/api'
    _DISTS_PREFIX = 'distributions/'
    _SECTIONS_PREFIX = 'sections/'
    _ACTIONS_PREFIX = 'actions/'
    _INSTANCES_SUFFIX = 'package-instances/'
    _PACKAGES_PREFIX = '/packages/'
    _LOGIN_PREFIX = 'sessions/'
    
    def __init__(self, url=None, username=None, password=None, timeout=None, httpclient_type=None):
        """
        Constructor to set up an API connection
        
        url -- URL to Apt repo server (defaults to _DEFAULT_API_URL)
        username -- Optional username for authentication
        password -- Optional password for authentication
        timeout -- Optional timeout (in seconds)
        """
        
        # set the url
        urlprefix = self._DEFAULT_API_URL
        if url:
            urlprefix = url

        # setup the client        
        client_factory = httpclient.HttpClientFactory()
        self.client = client_factory.create_client(baseurl=urlprefix, 
                                                   timeout=timeout,
                                                   name_implementation=httpclient_type)
        
        # attempt to authenticate if credentials were supplied
        self.sessiontoken = None
        if username and password:
            self.login(username, password)
    
    
    def login(self, username, password):
        """
        Authenticates the client
        
        username -- Optional username for authentication
        password -- Optional password for authentication
        """
        credentials = {'username': username, 'password': password}
        self.sessiontoken = self._post_request(self._LOGIN_PREFIX, credentials)
        
    def logout(self):
        """
        Logs the client out
        """
        self._delete_request(self._LOGIN_PREFIX + self.sessiontoken)
        
    def is_authenticated(self):
        """
        Returns True if this client's session has been authenticated, False otherwise
        """
        return self.sessiontoken is not None
        

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
    
    
    def get_distribution_metadata(self, id):
        """
        Retrieves the metadata for a distribution
    
        id -- Integer unique identifier for the distribution
        OR 
        distribution -- Distribution name
        """
        url = self._DISTS_PREFIX + str(id)
        return self._get_request(url)
    
    def list_sections(self, distribution_id):
        """
        Retrieves a list of sections
        
        distribution_id -- List section in the selected distribution
        """
        url = self._DISTS_PREFIX + str(distribution_id) + '/' + self._SECTIONS_PREFIX
        return self._get_request(url)
    
    
    def get_section_data(self, id):
        """
        Retrieves the metadata for a repository section
        
        id -- Integer unique identifier for the section
        OR        
        distribution_name -- Distribution name
        section_name -- Section name
        """
        return self._get_request(self._section_url(id))


    def list_section_packages(self, id):
        """
        Retrieves the list of packages for a repository section
        
        id -- Integer unique identifier for the section
        OR        
        distribution_name -- Distribution name
        section_name -- Section name
        """
        return self._get_request(self._section_url(id) + '/' + self._INSTANCES_SUFFIX)
        
    def get_package_instance(self, 
                             package_instance_id=None, 
                             section_id=None, 
                             name=None, version=None, architecture=None):
        url = None
        if package_instance_id:
            url = self._INSTANCES_SUFFIX + '/' + str(package_instance_id)
        else:
            url = '{0}{1}/{2}deb822/{3}/{4}/{5}'.format(self._SECTIONS_PREFIX,
                                                          section_id,
                                                          self._INSTANCES_SUFFIX,
                                                          name, version, architecture)
        return self._get_request(url)
        
    def upload_package(self, section_id, filename=None, fileobj=None):
        """
        Uploads a package
        
        filename -- filename of file to upload
        fileobj -- file object of file to upload
        """
        url = self._section_url(section_id) + '/' + self._INSTANCES_SUFFIX
        data = {}
        data['file'] = httpclient.PostDataFileObject(filename=filename, fileobj=fileobj)
        return self._post_request(url, data)
                
    def copy_package(self, src_instance_id, dest_section_id):
        """
        Copies a package instance
        
        src_instance_id - instance id of the source package to copy
        dest_section_id - destination section id to create new instance
        """
        url = self._section_url(dest_section_id) + '/' + self._INSTANCES_SUFFIX
        self._post_request(url, {'id': src_instance_id})
        
        
    def delete_package_instance(self, instance_id):
        """
        Deletes a package instance from a section
        
        instance_id -- id of instance to delete
        """
        url = self._INSTANCES_SUFFIX + str(instance_id)
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
        min_timestamp -- Lower bound on timestamp
        max_timestamp -- Upper bound on timestamp 
        max_items -- maximum number of actions to retrieve
        """
        url = ''
        if 'distribution_id' in kwargs:
            if 'section_id' in kwargs:
                url = '{0}{1}/{2}{3}/{4}'.format(self._DISTS_PREFIX, kwargs['distribution_id'],
                                                       self._SECTIONS_PREFIX, kwargs['section_id'],
                                                       self._ACTIONS_PREFIX)
            else:
                url = '{0}{1}/{2}'.format(self._DISTS_PREFIX, kwargs['distribution_id'],
                                                       self._ACTIONS_PREFIX)
        elif 'section_id' in kwargs:
            url = '{0}{1}/{2}'.format(self._SECTIONS_PREFIX, kwargs['section_id'],
                                                   self._ACTIONS_PREFIX)
        else:
            url = self._ACTIONS_PREFIX
        
        restrictions = {}
        for k in ('min_timestamp', 'max_timestamp', 'max_items'): 
            if k in kwargs:
                restrictions[k] = kwargs[k]
            
        if len(restrictions) > 0:
            url = url + '?' + urllib.urlencode(restrictions)
            
        return self._get_request(url)
        
            
    def _package_url(self, id=None, name=None, version=None, architecture=None):
        """
        Constructs an URL for a package
        
        id -- Integer unique identifier for the Debian package
        OR
        name -- Debian package name (Package)
        version -- Package version string
        architecture -- Architecture string for package (i386, amd64, all, etc.)
        """
        url = self._PACKAGES_PREFIX
        if id:
            url = url + str(id)
        elif name and version and architecture:
            url = url + '{0}/{1}/{2}'.format(name, version, architecture)
        else:
            raise AptRepoClientException(
                'Must specify either \'id\' or \'name,version,architecture\' for package')
            
        return url    
    
    def _section_url(self, id):
        """
        Constructs an URL for a section
        
        id -- Integer unique identifier for the section
        """
        return self._SECTIONS_PREFIX + str(id)

    def _get_request(self, url):
        """
        Internal method for GET requests
        """
        page = self.client.get(url)
        return json.loads(page)
    
    def _post_request(self, url, data):
        """
        Internal method for POST requests
        """
        page = self.client.post(url, data)
        return json.loads(page)

    def _delete_request(self, url):
        """
        Internal method for DELETE requests
        """
        self.client.delete(url)
