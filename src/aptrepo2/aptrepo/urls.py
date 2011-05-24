from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    # Web forms
    (r'^packages/$', 'aptrepo.views.packages'),
    (r'^packages/upload', 'aptrepo.views.upload_file'),
    (r'^packages/success', 'aptrepo.views.upload_success'),
    
    # Apt repo metafiles
    (r'^dists/{0}'.format(settings.APTREPO_FILESTORE['gpg_publickey']), 'aptrepo.views.gpg_public_key'),
    url(r'^dists/(?P<path>.*)', 'django.views.static.serve',
        {
            'document_root': settings.MEDIA_ROOT + '/' + settings.APTREPO_FILESTORE['metadata_subdir'],
        }
    ),
        
    # Static package files
    url(r'^packages/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT + '/' + settings.APTREPO_FILESTORE['packages_subdir'],
        }
    ),
)
