from functools import wraps
import httplib
import logging
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
import django.contrib.auth.views
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from server.aptrepo import models
from server.aptrepo.util import AuthorizationException, constants
from server.aptrepo.views import get_repository_controller


class UploadPackageForm(forms.Form):
    """
    Form class for package uploads
    """
    file = forms.FileField()
    section = forms.ModelChoiceField(queryset=models.Section.objects.all())
    comment = forms.CharField(required=False, max_length=models.Action.MAX_COMMENT_LENGTH)
    
class Breadcrumb():
    def __init__(self, description, link):
        self.description = description
        self.link = link
        
    def get_html_tag(self):
        if self.link:
            return '<a href="{link}">{description}</a>'.format(description=self.description, link=self.link)
        else:
            return self.description

def handle_exception(request_handler_func):
    """
    Decorator function for handling exceptions and converting them
    to the appropriate response for the web client
    """
    @wraps(request_handler_func)
    def wrapper_handler(*args, **kwargs):
        logger = logging.getLogger(settings.DEFAULT_LOGGER)

        try:
            return request_handler_func(*args, **kwargs)
        except ObjectDoesNotExist as e:
            logger.info(e)
            return HttpResponse(str(e), 
                                content_type='text/plain', 
                                status=httplib.NOT_FOUND)
        except AuthorizationException as e:
            logger.info(e)
            return HttpResponse(str(e), 
                                content_type='text/plain', 
                                status=httplib.UNAUTHORIZED)
        except Exception as e:
            logger.exception(e)
            if settings.DEBUG:
                raise e
            else:
                return HttpResponse(str(e), 
                                    content_type='text/plain', 
                                    status=httplib.INTERNAL_SERVER_ERROR)
    
    return wrapper_handler

@handle_exception
@require_http_methods(["GET"])
def repository_home(request):
    """
    Outputs the home page
    """
    menu_items_list = [ 
        (_('Browse Repository'), _('Browse the packages in the repository'), 'dists/', 'browse'),
        (_('Recent Activity'), _('Review the change history in the repository'), 'rss/', 'scroll'),
        (_('Download Public Key'), _('Download the GPG public key used for signing metadata'), 'dists/publickey.gpg', 'key'),
        (_('Administration'), _('Manage your repository (requires administrative privileges)'), 'admin/', 'admin'),
        (_('Help'), _('Documentation for using the repository'), 'help/', 'help')
    ]
    
    return render_to_response('aptrepo/home.html', 
                              {'menu_items': menu_items_list, 'breadcumbs': [] }, 
                              context_instance=RequestContext(request))
    

def login(request):
    """
    Performs user login
    """
    breadcrumbs = [ Breadcrumb(_('Logon'), None) ]
    return django.contrib.auth.views.login(request=request, template_name='aptrepo/login.html', 
                                           extra_context={ 'breadcumbs': breadcrumbs, 'next': '/aptrepo/' })

def logout(request):
    """
    Logs the user out
    """
    breadcrumbs = [ Breadcrumb(_('Logout'), None) ]    
    return django.contrib.auth.views.logout(request=request, template_name='aptrepo/logout.html',
                                            extra_context={ 'breadcumbs': breadcrumbs})

@handle_exception
@require_http_methods(["GET"])
def gpg_public_key(request):
    """
    Retrieves the GPG public key
    """
    repository = get_repository_controller(request=request)
    return HttpResponse(repository.get_gpg_public_key())

@handle_exception
@require_http_methods(["GET", "POST"])
def packages(request):
    """ 
    Handles package requests (no UI) 
    """
    if request.method == 'POST':
        return _packages_post(request)
    
    elif request.method == 'GET':
        # Get method at root will list all packages
        package_list = models.Package.objects.all().order_by('package_name')
        return render_to_response('aptrepo/packages_index.html', {'packages': package_list})
    
@handle_exception
@require_http_methods(["GET"])
def section_contents_list(request, distribution, section):
    section_obj = models.Section.objects.get(distribution__name=distribution, name=section)
    instances = models.PackageInstance.objects.filter(section=section_obj)
    return render_to_response('aptrepo/section_contents.html', 
                              { 'section' : section_obj, 
                                'package_instances': instances} )

def upload_success(request):
    """
    Successful upload view
    """
    return HttpResponse(_('Package successfully uploaded.'))


def remove_success(request):
    """
    Successful removal view
    """
    return HttpResponse(_('Package successfully removed.'))


@handle_exception
@require_http_methods(["GET", "POST"])
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
            comment = form.cleaned_data['comment']
            return _handle_uploaded_file(request,
                                         section.distribution.name,
                                         section.name, 
                                         request.FILES['file'],
                                         comment)

    elif request.method == 'GET':
        form = UploadPackageForm()
        
    return render_to_response('aptrepo/upload_package.html', {'form':form}, 
                              context_instance=RequestContext(request))
    
    
@handle_exception
@require_http_methods(["POST"])
@login_required
def delete_package_instance(request):
    """
    Basic HTTP POST call to remove a package instance
    """
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
        package_instance_id = package_instance.id
        
    return _handle_remove_package(request, package_instance_id)

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

@handle_exception
@require_http_methods(["POST"])
@login_required
def _packages_post(request):
    """ 
    POST requests will upload a package and create a new record 
    (separate internal method to enforce authentication only for POST, not GET)
    """
    uploaded_file = request.FILES['file']
    distribution = request.POST['distribution']
    section = request.POST['section']
    comment = request.POST['comment']

    # store result and redirect to success page
    return _handle_uploaded_file(request, distribution, section, uploaded_file, comment)

def _handle_uploaded_file(request, distribution_name, section_name, uploaded_file, comment):
    """ 
    Handles a successfully uploaded files 
    """
    # add the package
    repository = get_repository_controller(request=request)
    repository.add_package(distribution_name=distribution_name, section_name=section_name, 
                           uploaded_package_file=uploaded_file, comment=comment)
    return HttpResponseRedirect(reverse(upload_success))
    
def _handle_remove_package(request, package_instance_id):
    """
    Handles removing packages
    """
    repository = get_repository_controller(request=request)
    repository.remove_package(package_instance_id)
    return HttpResponseRedirect(reverse(remove_success))
