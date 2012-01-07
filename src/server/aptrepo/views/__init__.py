from django.conf import settings
from server.aptrepo.util.system import get_repository_version

def get_repository_controller(logger=None, request=None, sys_user=False):
    """
    Returns an instance to the repository controller
    
    logger - (optional) overrides the default logger
    """
    import repository
    return repository.Repository(logger=logger, request=request, sys_user=sys_user)

def common_template_variables(request):
    """
    Adds additional context variables for template processing
    """
    webmaster = dict()
    webmaster['name'], webmaster['email'] = settings.ADMINS[0]
    
    return {
        'repository_version': '.'.join(get_repository_version()),             
        'webmaster': webmaster,
    }
