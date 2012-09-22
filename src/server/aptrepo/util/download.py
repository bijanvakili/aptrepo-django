import os
import shutil
import tempfile
import urllib2
import urlparse
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


_SUPPORTED_DOWNLOAD_URL_SCHEMES = ['http', 'https']


class TemporaryDownloadedFile:
    """
    Encapsulates a temporary file download
    """
    
    def __init__(self, url):
        self._url = url
        self._fh = None
        self._filename = None

    def download(self):
        """
        Downloads content to a temporary file
        
        Returns the file handle
        """
        fh_download = urllib2.urlopen(self._url)
        tmp_pkg_fd, self._filename = tempfile.mkstemp(suffix='.deb', prefix='downloaded')
        self._fh = os.fdopen(tmp_pkg_fd, 'wb+')
        shutil.copyfileobj(fh_download, self._fh)
        self._fh.flush()
        os.fsync(tmp_pkg_fd)
        self._fh.close()

        self._fh = open(self._filename, 'r')
        return self._fh


    def close(self):
        """
        Safely closes the file handle and removes the temporary file
        """
        if self._fh:
            self._fh.close()
        if self._filename:
            os.remove(self._filename)
    

    def get_fh(self):
        """
        Returns the file handle
        """
        return self._fh
    
    def get_path(self):
        """
        Returns the path to the temporary file
        """
        return self._filename
    
    def get_size(self):
        """
        Returns the total size of the temporary file
        """
        return os.path.getsize(self.get_path())
    
    

def validate_download_url(url):
    """
    Determines if an URL is valid for downloads
    """
    parse_result = urlparse.urlparse(url)
    if parse_result.scheme not in _SUPPORTED_DOWNLOAD_URL_SCHEMES:
        raise ValidationError(_(u'Invalid URL specified: %s' % url))
