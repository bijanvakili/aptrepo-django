from django.conf.urls.defaults import *
from django.conf import settings

# TODO Load 'packages' and 'dists' prefixes from settings 

urlpatterns = patterns('',
    # Web forms
    (r'^packages/$', 'aptrepo.views.packages'),
    (r'^packages/upload', 'aptrepo.views.upload_file'),
    (r'^packages/upload_success', 'aptrepo.views.upload_success'),
    (r'^packages/delete', 'aptrepo.views.delete_package_instance'),
    (r'^packages/delete_success', 'aptrepo.views.remove_success'),
    
    # Apt repo metafiles
    (r'^dists/{0}'.format(settings.APTREPO_FILESTORE['gpg_publickey']), 
        'aptrepo.views.gpg_public_key'),
    (r'^dists/(?P<distribution>\w+)/(?P<section>\w+)/binary-(?P<architecture>\w+)/Packages(?P<extension>.*)',
        'aptrepo.views.package_list'),
    (r'^dists/(?P<distribution>\w+)/Release(?P<extension>.*)', 
        'aptrepo.views.release_list'),
    
    # Static package files
    url(r'^(public/){0,1}packages/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT + '/' + settings.APTREPO_FILESTORE['packages_subdir'],
        }
    ),
)
