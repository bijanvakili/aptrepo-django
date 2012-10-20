from django.views.decorators.http import require_http_methods
from server.aptrepo.views import get_repository_controller
from django.http import HttpResponse
from server.aptrepo.util import constants
from server.aptrepo.views.decorators import handle_exception

@handle_exception
@require_http_methods(["GET"])
def gpg_public_key(request):
    """
    Retrieves the GPG public key (as a file download)
    """
    repository = get_repository_controller(request=request)
    response = HttpResponse(repository.get_gpg_public_key())
    response['Content-Disposition'] = "attachment" 
    return response


@handle_exception
@require_http_methods(["GET"])
def package_list(request, distribution, section, architecture, extension=None):
    """
    Retrieve a package list
    """
    # TODO caching of HTML rendering of package list 
              
    is_compressed = False
    if extension == constants.GZIP_EXTENSION:
        is_compressed = True
    elif extension != '':
        return HttpResponse(status_code=404)
        
    mimetype = 'text/plain'
    if is_compressed:
        mimetype = 'application/gzip'
    repository = get_repository_controller(request=request)
    response = HttpResponse(mimetype=mimetype)
    response.content = repository.get_packages(distribution, section, architecture,
                                               is_compressed)
    response['Content-Length'] = len(response.content)
    if is_compressed:
        response['Content-Encoding'] = 'gzip'
        
    return response
        

@handle_exception
@require_http_methods(["GET"])
def release_list(request, distribution, extension):
    """
    Retrieves a Releases metafile list
    """
    repository = get_repository_controller(request=request)
    (releases_data, signature_data) = repository.get_release_data(distribution)
    data = None
    if extension == constants.GPG_EXTENSION:
        data = signature_data
    else:
        data = releases_data

    # return the response
    return HttpResponse(data, mimetype = 'text/plain')
