from django.conf.urls.defaults import *
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^aptrepo2/', include('aptrepo2.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^admin/', include(admin.site.urls)),
    (r'^aptrepo/api/', include('aptrepo.views.api.urls')),
    (r'^aptrepo/', include('aptrepo.views.webpages.urls')),
)
