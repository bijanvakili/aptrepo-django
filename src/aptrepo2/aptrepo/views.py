from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from aptrepo2.settings import APTREPO_FILESTORE_ROOT
import models
from common import AptRepoException


fs = FileSystemStorage(location=APTREPO_FILESTORE_ROOT)

def upload_file(request):
    
    """ handles uploading a file """
    try:
        if request.method != 'POST':
            raise AptRepoException('Invalid HTTP method')
            
        uploaded_file = request.FILES['attachment']
        
        fs.delete(uploaded_file.name)
        new_file_path = fs.save(name=uploaded_file.name, content=uploaded_file)
        new_file_path = fs.path(new_file_path)
        package = models.Package.load_fromfile(new_file_path)

        # store result and redirect to success page        
        package.save() 
        return HttpResponseRedirect(reverse('aptrepo.views.success'))
    
    except Exception as e:
        return HttpResponse(content=e.__str__(), status=406)


def success(request):
    return HttpResponse("Package successfully uploaded.")
