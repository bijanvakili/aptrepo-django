from django.conf import settings
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


def constrain_queryset(request, query_set, default_limit=None):
    """
    Constrain a DB query result based on common HTTP parameters:

    request -- HTTP request
    query_set -- query set to constrain
    default_limit -- default query limit (defaults to first entry in settings.APTREPO_PAGINATION_LIMITS) 

    With 'request', the following GET parameters are used:
    request.GET['offset'] -- Start of the range (defaults to 0)
    request.GET['limit'] -- Maximum number of items to return (defaults to 'default_limit')
    request.GET['descending'] -- Should the results should be in reverse order (defaults to False)
    """
    if not default_limit:
        default_limit = settings.APTREPO_PAGINATION_LIMITS[0]
    
    min = 0
    if 'offset' in request.GET:
        min = int(request.GET['offset']) 
    
    max = min + default_limit
    if 'limit' in request.GET:
        max = min + int(request.GET['limit'])
    
    result_set = query_set[min:max]
    if 'descending' in request.GET and request.GET['descending']:
        result_set = result_set.reverse()
        
    return result_set
