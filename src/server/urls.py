from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings


admin.autodiscover()

urlpatterns = patterns('',
    # Uncomment the admin/doc line below to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^aptrepo/admin/', include(admin.site.urls)),
    (r'^aptrepo/api/', include('aptrepo.views.api.urls')),
    (r'^aptrepo/', include('aptrepo.views.webpages.urls')),
    
    # static files
    url(r'^aptrepo/public/(?P<path>.*)$', 'django.views.static.serve', 
        {
            'document_root': settings.MEDIA_ROOT,
        }
    ),
)
