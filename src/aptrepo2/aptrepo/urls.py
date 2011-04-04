from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^package/upload', 'aptrepo.views.upload_file'),
    (r'^package/success', 'aptrepo.views.success')
)
