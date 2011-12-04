from django.utils.translation import ugettext as _

class AptRepoException(Exception):
    """ 
    Exceptions for the apt repo
    """
    
    message = _('Unknown error')
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return self.message


class AuthorizationException(AptRepoException):
    """
    Exception for authorization failures  
    """
    
    def __init__(self, message=None):
        if not message:
            message = _('Not authorized')
        
        super(AuthorizationException, self).__init__(message)
