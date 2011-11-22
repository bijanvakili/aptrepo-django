
class AptRepoException(Exception):
    """ 
    Exceptions for the apt repo
    """
    
    message = "(Unknown error)"
    
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
            message = "Not authorized"
        
        super(AuthorizationException, self).__init__(message)
