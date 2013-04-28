from django.conf.urls import patterns, include 
from django.contrib import admin
from django.shortcuts import redirect


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
    (r'^aptrepo/web/', include('aptrepo.views.webpages.urls', namespace='aptrepo')),
    (r'^aptrepo/$', lambda request: redirect(request.path + 'web/')),
    (r'^aptrepo$', lambda request: redirect(request.path + '/web/')),
)
