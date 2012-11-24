from django.conf.urls.defaults import *
from django.conf import settings
from feeds import DistributionAtomFeed, DistributionRSSFeed, \
    RepositoryRSSFeed, RepositoryAtomFeed, \
    SectionRSSFeed, SectionAtomFeed


# repository history URLs
repository_history_urls = patterns('',
    url(r'^$', 'aptrepo.views.webpages.pages.history', name='all_history'),
    url(r'^rss/{0,1}$', RepositoryRSSFeed()),
    url(r'^atom/{0,1}$', RepositoryAtomFeed()),
)


# /distributions/ URLs
distribution_urls = patterns('aptrepo.views.webpages.pages',
    
    # distirbution history
    url(r'^(?P<distribution>\w+)/history/$','history'),
    url(r'^(?P<distribution>\w+)/history/rss/{0,1}$', DistributionRSSFeed()),
    url(r'^(?P<distribution>\w+)/history/atom/{0,1}$', DistributionAtomFeed()),
          
    # section listing                       
    url(r'^(?P<distribution>\w+)/sections/(?P<section>\w+)/{0,1}$',
        'section_contents_list', name='section_contents'),

    # section history
    url(r'^(?P<distribution>\w+)/sections/(?P<section>\w+)/history/{0,1}$', 'history'),
    url(r'^(?P<distribution>\w+)/sections/(?P<section>\w+)/history/rss/{0,1}$', SectionRSSFeed()),
    url(r'^(?P<distribution>\w+)/sections/(?P<section>\w+)/history/atom/{0,1}$', SectionAtomFeed()),

    # direct upload to section                  
    (r'^(?P<distribution_name>\w+)/sections/(?P<section_name>\w+)/upload/{0,1}$',
        'upload'),
                             
    # browse distribution page and Ajax call                   
    url(r'^(?P<distribution_name>\w+)/$', 'get_distribution_info', name='distribution_info'),
    url(r'^$', 'browse_distributions', name='browse_distributions'),
)

# Web forms/pages for packages
package_urls = patterns('aptrepo.views.webpages.pages',
    # TODO /packages/ URL hierarchy needs to be revised
    url(r'^upload_success', 'upload_success', name='package_upload_success'),
    url(r'^delete_success', 'remove_success', name='package_delete_success'),

    url(r'^upload', 'upload', name='package_upload'),    
    url(r'^delete', 'delete_package_instance', name='package_delete'),
) 


urlpatterns = patterns('',
                       
    url(r'^$', 'aptrepo.views.webpages.pages.repository_home', name='repository_home'),
    url(r'^login/$', 'aptrepo.views.webpages.pages.login', name='login'),
    url(r'^logout/$', 'aptrepo.views.webpages.pages.logout', name='logout'),
    url(r'^help/$', 'aptrepo.views.webpages.pages.help', name='help'),
    url(r'^history/', include(repository_history_urls)),
    url(r'^distributions/', include(distribution_urls)),
    url(r'^packages/', include(package_urls)),                       
    
    # static files
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.STATIC_ROOT,
        }
    ),
)
