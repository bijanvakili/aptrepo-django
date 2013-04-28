from django.conf.urls import include, patterns, url
from django.conf import settings

# Apt repository metafiles
aptrepo_metadata_urls = patterns('aptrepo.views.repo.files',

    # Package(.gz)
    (r'^(?P<distribution>\w+)/(?P<section>\w+)/binary-(?P<architecture>\w+)/Packages(?P<extension>.*)',
        'package_list'),
                                 
    # Release
    (r'^(?P<distribution>\w+)/Release(?P<extension>.*)', 
        'release_list'),
)

urlpatterns = patterns('',
    (r'^keys/publickey.gpg$', 'aptrepo.views.repo.files.gpg_public_key'),

    url(r'^dists/', include(aptrepo_metadata_urls)),
    # Debian package files (can include 'public' prefix or not)

    url(r'^packages/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT + '/' + settings.APTREPO_FILESTORE['packages_subdir'],
        }
    ),
)        
