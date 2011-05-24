from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django import forms
from django.conf import settings
import models
from common import AptRepoException
from repository import Repository


class UploadPackageForm(forms.Form):
    """
    Form class for package uploads
    """
    file = forms.FileField()
    section = forms.ModelChoiceField(queryset=models.Section.objects.all())

def gpg_public_key(request):
    """
    Retrieves the GPG public key
    """
    try:
        if request.method != 'GET':
            raise AptRepoException('Invalid HTTP method')
        
        repository = Repository()
        return HttpResponse(repository.get_gpg_public_key())

    except Exception as e:
        return _error_response(e)

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


def _handle_uploaded_file(distribution_name, section_name, uploaded_file):
    """ 
    Handles a successfully uploaded files 
    """
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
