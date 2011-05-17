from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^packages/$', 'aptrepo.views.packages'),
    (r'^packages/upload', 'aptrepo.views.upload_file'),
    (r'^packages/success', 'aptrepo.views.upload_success'),
    (r'^dists/(?P<distribution>\w+)/(?P<section>\w+)/binary-(?P<architecture>\w+)/Packages(?P<extension>.*)',
     'aptrepo.views.get_package_list'),
    (r'^dists/(?P<distribution>\w+)/Release(?P<extension>.*)', 'aptrepo.views.get_release_data'),
    
    url(r'^public/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT,
        }
    ),
)
