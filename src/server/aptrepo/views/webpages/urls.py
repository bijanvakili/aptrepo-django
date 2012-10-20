from django.conf.urls.defaults import *
from django.conf import settings
from feeds import *

# Web forms/pages for packages
package_urls = patterns('aptrepo.views.webpages.pages',
    (r'^$', 'packages'),
    (r'^upload', 'upload'),
    (r'^delete_success', 'remove_success'),
    (r'^delete', 'delete_package_instance'),
) 


# /dists/ URLs
aptrepo_dists_urls = patterns('aptrepo.views.webpages.pages',
    (r'^$', 'browse_distributions'),
    (r'^(?P<distribution_id>\d+)/$',
        'get_distribution_info'),
    (r'^(?P<distribution>\w+)/(?P<section>\w+)/{0,1}$',
        'section_contents_list'),
    (r'^(?P<distribution_name>\w+)/(?P<section_name>\w+)/upload/{0,1}$',
        'upload'),
)

urlpatterns = patterns('',
                       
    (r'^$', 'aptrepo.views.webpages.pages.repository_home'),
    url(r'^login/$', 'aptrepo.views.webpages.pages.login'),
    url(r'^logout/$', 'aptrepo.views.webpages.pages.logout'),
    url(r'^packages/', include(package_urls)),
    url(r'^dists/', include(aptrepo_dists_urls)),
    url(r'^rss/{0,1}$', RepositoryRSSFeed()),
    url(r'^rss/(?P<distribution>\w+)/{0,1}$', DistributionRSSFeed()),
    url(r'^rss/(?P<distribution>\w+)/(?P<section>\w+)/{0,1}$', SectionRSSFeed()),
    url(r'^atom/{0,1}$', RepositoryAtomFeed()),
    url(r'^atom/(?P<distribution>\w+)/{0,1}$', DistributionAtomFeed()),
    url(r'^atom/(?P<distribution>\w+)/(?P<section>\w+)/{0,1}$', SectionAtomFeed()),
    url(r'^history/{0,1}$', 'aptrepo.views.webpages.pages.history'),
    url(r'^history/(?P<distribution>\w+)/{0,1}$', 'aptrepo.views.webpages.pages.history'),
    url(r'^history/(?P<distribution>\w+)/(?P<section>\w+)/{0,1}$', 'aptrepo.views.webpages.pages.history'),
    url(r'^upload_success', 'aptrepo.views.webpages.pages.upload_success'),    
)
