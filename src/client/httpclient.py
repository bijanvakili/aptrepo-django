#!/usr/bin/env python

import abc

"""
Module that supports multiple implementations of an HTTP client
(depending on 3rd party module availability)
"""

class HttpClientException(Exception):
    """ 
    Exceptions for the HTTP client
    """
    
    message = "(Unknown error)"
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return repr(self.message)
    

class HttpImplementationInfo:
    """
    Information for an HTTP implementation
    """
    def __init__(self, name, available=False):
        self.name = name
        self.available = available

# TODO Determine if the import tests can be moved into HttpClientFactory


"""
http client library implementations

1) Django test client (default)
2) cURL
3) Python urllib(2)
"""
E_DJANGO, E_PYCURL, E_URLLIB = range(3)
_HTTP_IMPLEMENTATION_INFO = { 
    E_DJANGO : HttpImplementationInfo('django.test'), 
    E_PYCURL : HttpImplementationInfo('pycurl'), 
    E_URLLIB : HttpImplementationInfo('urllib'), 
}
try:
    import django.test
    _HTTP_IMPLEMENTATION_INFO[E_DJANGO].available = True
except ImportError:
    _HTTP_IMPLEMENTATION_INFO[E_DJANGO].available = False
    

try:
    import urllib2
    import poster
    _HTTP_IMPLEMENTATION_INFO[E_URLLIB].available = True
except ImportError:
    _HTTP_IMPLEMENTATION_INFO[E_URLLIB].available = False

try:
    import pycurl
    import StringIO
    _HTTP_IMPLEMENTATION_INFO[E_PYCURL].available = True
except ImportError:
    _HTTP_IMPLEMENTATION_INFO[E_PYCURL].available = False        


class HttpClientBase(object):
    """
    Abstract base class for an HTTP client
    """
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, baseurl, timeout):
        self.baseurl = baseurl
        self.timeout = timeout
    
    @abc.abstractmethod
    def get(self, url):
        """
        GET request
        
        url -- encoded string URL to retrieve
        """
        return
    
    @abc.abstractmethod
    def post(self, url, data):
        """
        POST request
        
        url -- encoded string URL
        data -- dict specifying parameterized data to post 
        """
        return
    
    @abc.abstractmethod
    def delete(self, url):
        """
        DELETE request
        
        url -- encoded string URL of resource to delete
        """        
        return
    
    def _compute_url(self, url):
        """
        Internal function to compute the actual URL
        """
        if self.baseurl:
            return self.baseurl + '/' + url
        else:
            return url
    


class HttpClientFactory:
    """
    Factory class to construct an HTTP client
    """
   
    def __init__(self):
        pass
    
    def create_client(self, baseurl, id_implementation=None, name_implementation=None, timeout=None):
        """
        Construct a new HTTP client
        
        id_implementation -- Optional integer ID of client implementation (see above)
        name_implemenation -- Optional name of implementation (see above)
        """
        
        if id_implementation is not None:
            if id_implementation >= len(_HTTP_IMPLEMENTATION_INFO):
                raise HttpClientException('Unknown implementation ID: {0}'.format(id_implementation))
        elif name_implementation:
            for id,info in _HTTP_IMPLEMENTATION_INFO.items():
                if info.name == name_implementation:
                    id_implementation = id
            
            if not id_implementation:
                raise HttpClientException('HTTP implementation not found: {0}'.format(name_implementation)) 
                
            
        # Search for the first available implementation if none was found
        if not id_implementation:
            for id, info in _HTTP_IMPLEMENTATION_INFO.items():
                if info.available:
                    id_implementation = id
                    break 
            
            if id_implementation is None:
                raise HttpClientException('No implementation available')

        
        # instantiate the appropriate client
        httpclient = None
        if id_implementation == E_DJANGO:
            httpclient = DjangoClient(baseurl, timeout)
        elif id_implementation == E_PYCURL:
            httpclient = PyCurlClient(baseurl, timeout)
        elif id_implementation == E_URLLIB:
            httpclient = UrlLibClient(baseurl, timeout)
            
        return httpclient
    
    
class DjangoClient(HttpClientBase):
    """
    Django test client implementation
    """
    def __init__(self, baseurl, timeout):
        super(DjangoClient, self).__init__(baseurl, timeout)
        self.client = django.test.Client()
        
    def get(self, url):
        response = self.client.get(self._compute_url(url))
        if response.status_code != 200:
            self._raise_with_statuscode(response.status_code) 
        return response.content

    def post(self, url, data):
        response = self.client.post(self._compute_url(url), data)        
        if response.status_code != 200:
            self._raise_with_statuscode(response.status_code) 
        return response.content
 
    def delete(self, url):
        response = self.client.delete(self._compute_url(url))
        if response.status_code != 204:
            self._raise_with_statuscode(response.status_code) 
        
        
    def _raise_with_statuscode(self, status_code):
        raise HttpClientException('Status code: {0}'.format(status_code))
    

class PyCurlClient(HttpClientBase):
    """
    PyCurl test client implementation
    """
    def __init__(self, baseurl, timeout):
        super(PyCurlClient, self).__init__(baseurl, timeout)
                
    def get(self, url):
        (client, response_buffer) = self._make_client(url)
        client.setopt(pycurl.HTTPGET, True)
        client.perform()
        return response_buffer.getvalue()
    
    def post(self, url, data):
        (client, response_buffer) = self._make_client(url)
        client.setopt(pycurl.POST, True)
        client.setopt(pycurl.HTTPPOST, data)
        client.perform()
        return response_buffer.getvalue()
    
    def delete(self, url):
        (client, response_buffer) = self._make_client(url)        
        client.setopt(pycurl.CUSTOMREQUEST, 'DELETE')
        client.perform()
        return response_buffer.getvalue()
        
    def _make_client(self, url):
        """
        Internal functional to setup curl
        
        Return (client, response_buffer)
        """
        client = pycurl.Curl()
        client.setopt(pycurl.URL, self._compute_url(url))
        client.setopt(pycurl.TIMEOUT, self.timeout)
        response_buffer = StringIO.StringIO()
        client.setopt(pycurl.WRITEFUNCTION, buffer)
        return (client, response_buffer)


class UrlLibClient(HttpClientBase):
    
    class HTTPDeleteRequest(urllib2.Request):
        """
        Derived class for making HTTP DELETE requests
        """
        def get_method(self):
            return 'DELETE'    
    
    
    def __init__(self, baseurl, timeout):
        super(UrlLibClient, self).__init__(baseurl, timeout)

        # setup password authentication for REST connections
        handlers = []
        """
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, self.url, username, password)
        handlers.append(urllib2.HTTPBasicAuthHandler(password_manager))
        """
        handlers.append(poster.streaminghttp.get_handlers())
        self.urlclient = urllib2.build_opener(handlers)

    def get(self, url):
        """
        Internal method for GET requests
        """
        return self.urlclient.open(url=self._compute_url(url),  
                                   timeout=self.timeout)
    
    def _post_request(self, url, data):
        """
        Internal method for POST requests
        """
        datagen, headers = poster.encode.multipart_encode(data)
        request = urllib2.Request(url=self._compute_url(url), 
                                  data=datagen, headers=headers)
        return self.urlclient.open(url=request, timeout=self.timeout)


    def _delete_request(self, url):
        """
        Internal method for DELETE requests
        """
        request = self.HTTPDeleteRequest(url=self._compute_url(url))
        self.urlclient.open(url=request, timeout=self.timeout)
