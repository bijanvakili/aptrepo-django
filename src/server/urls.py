from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings


admin.autodiscover()

# Javascript translation packages
js_info_dict = {
    'packages' : ('aptrepo',) ,
}

# Top-level URLs
urlpatterns = patterns('',
    # Uncomment the admin/doc line below to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^jsi18n/$', 'django.views.i18n.javascript_catalog', js_info_dict),

    (r'^aptrepo/admin/', include(admin.site.urls)),
    (r'^aptrepo/api/', include('aptrepo.views.api.urls')),
    (r'^aptrepo/repository/', include('aptrepo.views.repo.urls')),
    (r'^aptrepo/', include('aptrepo.views.webpages.urls')),
    
    # static files
    url(r'^aptrepo/media/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.STATIC_ROOT,
        }
    ),
    url(r'^aptrepo/public/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT,
        }
    ),
)
