import httplib
import logging
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_protect
from django.template import RequestContext
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from server.aptrepo import models
from server.aptrepo.util import AptRepoException, AuthorizationException, constants
from server.aptrepo.views import get_repository_controller


class UploadPackageForm(forms.Form):
    """
    Form class for package uploads
    """
    file = forms.FileField()
    section = forms.ModelChoiceField(queryset=models.Section.objects.all())

class BadHTTPMethodException(AptRepoException):
    """
    Exception for requests with invalid HTTP methods (GET versus PUTS)  
    """
    
    def __init__(self, request=None):
        message = "Invalid HTTP method"
        if request:
            message = message + " (" + request.method + ")"
        super(BadHTTPMethodException, self).__init__(message)

def handle_exception(request_handler_func):
    """
    Decorator function for handling exceptions and converting them
    to the appropriate response for the web client
    """
    def wrapper_handler(*args, **kwargs):
        logger = logging.getLogger(settings.DEFAULT_LOGGER)

        try:
            return request_handler_func(*args, **kwargs)
        except BadHTTPMethodException as e:
            logger.info(e)
            return HttpResponse(str(e), 
                                content_type='text/plain', 
                                status=httplib.FORBIDDEN)
        except AuthorizationException as e:
            logger.info(e)
            return HttpResponse(str(e), 
                                content_type='text/plain', 
                                status=httplib.UNAUTHORIZED)
        except Exception as e:
            logger.exception(e)
            if settings.DEBUG:
                raise
            else:
                return HttpResponse(str(e), 
                                    content_type='text/plain', 
                                    status=httplib.INTERNAL_SERVER_ERROR)
    
    return wrapper_handler

@handle_exception
def gpg_public_key(request):
    """
    Retrieves the GPG public key
    """
    if request.method != 'GET':
        raise BadHTTPMethodException(request)
    
    repository = get_repository_controller(request=request)
    return HttpResponse(repository.get_gpg_public_key())

@handle_exception
def packages(request):
    """ 
    Handles package requests (no UI) 
    """
    if request.method == 'POST':
        return packages_post(request)
    
    elif request.method == 'GET':
        """ Get method at root will list all packages """
        package_list = models.Package.objects.all().order_by('package_name')
        return render_to_response('aptrepo/packages_index.html', {'packages': package_list})
                 
    else:
        raise BadHTTPMethodException(request)
    

@handle_exception
@login_required
def packages_post(request):
    """ POST requests will upload a package and create a new record """
    uploaded_file = request.FILES['file']
    distribution = request.POST['distribution']
    section = request.POST['section']

    # store result and redirect to success page
    return _handle_uploaded_file(request, distribution, section, uploaded_file)


def upload_success(request):
    """
    Successful upload view
    """
    return HttpResponse("Package successfully uploaded.")


def remove_success(request):
    """
    Successful removal view
    """
    return HttpResponse("Package successfully removed.")


@handle_exception
@login_required
@csrf_protect
def upload_file(request):
    """ 
    Provides a form to upload packages
    """
    if request.method == 'POST':
        form = UploadPackageForm(request.POST, request.FILES)
        if form.is_valid():
            section = form.cleaned_data['section']
            return _handle_uploaded_file(request,
                                         section.distribution.name,
                                         section.name, 
                                         request.FILES['file'])

    elif request.method == 'GET':
        form = UploadPackageForm()
        
    else:
        raise BadHTTPMethodException(request)

    return render_to_response('aptrepo/upload_package.html', {'form':form}, 
                              context_instance=RequestContext(request))
    
    
@handle_exception
@login_required
def delete_package_instance(request):
    """
    Basic HTTP POST call to remove a package instance
    """
    if request.method != 'POST':
        raise BadHTTPMethodException(request)
    
    # extract the package instance identifier
    package_instance_id = 0
    if 'package_instance' in request.POST:
        package_instance_id = request.POST['package_instance']
    else:
        package_instance = models.PackageInstance.objects.get(
            section__distribution__name=request.POST['distribution'],
            section__name=request.POST['section'],
            package__package_name=request.POST['name'],
            package__architecture=request.POST['architecture'],
            package__version=request.POST['version'])
        if package_instance is None:
            raise AptRepoException("Package instance not found for removal")
        package_instance_id = package_instance.id
        
    return _handle_remove_package(request, package_instance_id)

@handle_exception
def package_list(request, distribution, section, architecture, extension=None):
    """
    Retrieve a package list
    """
    if request.method != 'GET':
        raise BadHTTPMethodException(request)

    # NOTE: caching is not employed for package list
              
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
def release_list(request, distribution, extension):
    """
    Retrieves a Releases metafile list
    """
    if request.method != 'GET':
        raise BadHTTPMethodException(request)

    repository = get_repository_controller(request=request)
    (releases_data, signature_data) = repository.get_release_data(distribution)
    data = None
    if extension == constants.GPG_EXTENSION:
        data = signature_data
    else:
        data = releases_data

    # return the response
    return HttpResponse(data, mimetype = 'text/plain')


def _handle_uploaded_file(request, distribution_name, section_name, uploaded_file):
    """ 
    Handles a successfully uploaded files 
    """
    # add the package
    repository = get_repository_controller(request=request)
    repository.add_package(distribution_name=distribution_name, section_name=section_name, 
                           uploaded_package_file=uploaded_file)
    return HttpResponseRedirect(reverse(upload_success))
    
def _handle_remove_package(request, package_instance_id):
    """
    Handles removing packages
    """
    repository = get_repository_controller(request=request)
    repository.remove_package(package_instance_id)
    return HttpResponseRedirect(reverse(remove_success))
