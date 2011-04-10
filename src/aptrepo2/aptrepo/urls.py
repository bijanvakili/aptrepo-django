from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^packages/$', 'aptrepo.views.packages'),
    (r'^packages/upload', 'aptrepo.views.upload_file'),
    (r'^packages/success', 'aptrepo.views.upload_success')
)
