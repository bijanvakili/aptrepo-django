from django.http import HttpResponse
from django.utils.translation import ugettext as _

class DjangoSessionAuthentication(object):
    """
    Authentication handler that uses django sessions
    """
    
    def is_authenticated(self, request):
        """
        Enforces authentication for POST and DELETE requests
        """
        if request.method not in ('POST', 'DELETE'):
            return True
        
        if not request.user:
            return False
        
        return request.user.is_authenticated()
    
    def challenge(self):
        """
        Shows error message requiring authentication
        """
        resp = HttpResponse(_('Authentication Required'))
        resp.status_code = 401
        return resp
