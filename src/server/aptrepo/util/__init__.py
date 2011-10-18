
class AptRepoException(Exception):
    """ 
    Exceptions for the apt repo
    """
    
    message = "(Unknown error)"
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return self.message

