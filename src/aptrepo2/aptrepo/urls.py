from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^packages/$', 'aptrepo.views.packages'),
    (r'^packages/upload', 'aptrepo.views.upload_file'),
    (r'^packages/success', 'aptrepo.views.upload_success'),
    
    url(r'^public/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT,
        }
    ),
)
