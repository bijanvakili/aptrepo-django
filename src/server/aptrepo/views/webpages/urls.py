from django.conf.urls.defaults import *
from django.conf import settings
from feeds import DistributionFeed

# Web forms/pages for packages
package_urls = patterns('aptrepo.views.webpages.pages',
    (r'^$', 'packages'),
    (r'^upload_success', 'upload_success'),    
    (r'^upload', 'upload_file'),
    (r'^delete_success', 'remove_success'),
    (r'^delete', 'delete_package_instance'),
) 

# Apt repo metadata
aptrepo_metadata_urls = patterns('aptrepo.views.webpages.pages',
    (r'^{0}'.format(settings.APTREPO_FILESTORE['gpg_publickey']), 
        'gpg_public_key'),
    (r'^(?P<distribution>\w+)/(?P<section>\w+)/binary-(?P<architecture>\w+)/Packages(?P<extension>.*)',
        'package_list'),
    (r'^(?P<distribution>\w+)/Release(?P<extension>.*)', 
        'release_list'),
    (r'^(?P<distribution>\w+)/rss', DistributionFeed())
)

urlpatterns = patterns('',
    url(r'^login/$', 'django.contrib.auth.views.login',
        {
            'template_name': 'aptrepo/login.html'         
        }
    ),
    url(r'^packages/', include(package_urls)),
    url(r'^dists/', include(aptrepo_metadata_urls)),
                       
    # Debian package files
    url(r'^(public/){0,1}packages/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT + '/' + settings.APTREPO_FILESTORE['packages_subdir'],
        }
    ),
)
