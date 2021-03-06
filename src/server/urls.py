from django.conf.urls.defaults import *
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    # Uncomment the admin/doc line below to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^aptrepo/admin/', include(admin.site.urls)),
    (r'^aptrepo/api/', include('aptrepo.views.api.urls')),
    (r'^aptrepo/', include('aptrepo.views.webpages.urls')),
)
