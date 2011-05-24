import zlib 
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django import forms
from django.conf import settings
import models
from common import AptRepoException, GZIP_EXTENSION, GPG_EXTENSION
from repository import Repository



class UploadPackageForm(forms.Form):
    """
    Form class for package uploads
    """
    file = forms.FileField()
    section = forms.ModelChoiceField(queryset=models.Section.objects.all())


def packages(request):
    """ 
    Handles package requests (no UI) 
    """
    try:
        if request.method == 'POST':
            """ POST requests will upload a package and create a new record """
            uploaded_file = request.FILES['file']
            distribution = request.POST['distribution']
            section = request.POST['section']

            # store result and redirect to success page
            return _handle_uploaded_file(distribution, section, uploaded_file)
        
        elif request.method == 'GET':
            """ Get method at root will list all packages """
            package_list = models.Package.objects.all().order_by('package_name')
            return render_to_response('aptrepo/packages_index.html', {'packages': package_list})
                     
        else:
            raise AptRepoException('Invalid HTTP method')
    
    except Exception as e:
        return _error_response(e)


def upload_success(request):
    """
    Successful upload view
    """
    return HttpResponse("Package successfully uploaded.")


def upload_file(request):
    """ 
    Provides a form to upload packages
    """
    try:
        if request.method == 'POST':
            form = UploadPackageForm(request.POST, request.FILES)
            if form.is_valid():
                section = request.cleaned_data['section']
                return _handle_uploaded_file(section.distribution.name,
                                             section.name, 
                                             request.FILES['file'])

        elif request.method == 'GET':
            form = UploadPackageForm()
            
        else:
            raise AptRepoException('Invalid HTTP method')

        return render_to_response('aptrepo/upload_package.html', {'form':form}, 
                                  context_instance=RequestContext(request))
        
    except Exception as e:
        return _error_response(e)

def gpg_public_key(request):
    """
    Retrieve the GPG public key
    """
    try:
        if request.method != 'GET':
            raise AptRepoException('Invalid HTTP method')

        repository = Repository()
        return HttpResponse(repository.get_gpg_public_key())
    
    except Exception as e:
        return _error_response(e)
    

def package_list(request, distribution, section, architecture, extension=None):
    """
    Retrieve a package list
    """
    try:
        if request.method != 'GET':
            raise AptRepoException('Invalid HTTP method')

        # NOTE: caching is not employed for package list
        is_compressed = extension == GZIP_EXTENSION
        mimetype = 'text/plain'
        if is_compressed:
            mimetype = 'application/gzip'
        repository = Repository()
        response = HttpResponse(mimetype=mimetype)
        response.content = repository.get_packages(distribution, section, architecture,
                                                   is_compressed)
        response['Content-Length'] = len(response.content)
        if is_compressed:
            response['Content-Encoding'] = 'gzip'
            
        return response
    
    except Exception as e:
        return _error_response(e)
        

def release_list(request, distribution, extension):
    """
    Retrieves a Releases metafile list
    """
    try:
        if request.method != 'GET':
            raise AptRepoException('Invalid HTTP method')

        repository = Repository()
        (releases_data, signature_data) = repository.get_release_data(distribution)
        data = None
        if extension == GPG_EXTENSION:
            data = signature_data
        else:
            data = releases_data

        # return the response
        return HttpResponse(data)

    except Exception as e:
        return _error_response(e)

def _handle_uploaded_file(distribution_name, section_name, uploaded_file):
    """ 
    Handles a successfully uploaded files 
    """
    
    # add the package
    repository = Repository()
    repository.add_package(distribution_name, section_name, uploaded_file)
    return HttpResponseRedirect(reverse('aptrepo.views.upload_success'))
    

def _error_response(exception):
    """ 
    Error response 
    """
    if settings.DEBUG:
        raise exception
    else:
        return HttpResponse(content=exception.__str__(), status=406)
