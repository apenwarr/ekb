from django.conf.urls.defaults import *
import os
import ekb.views

urlpatterns = patterns('',
    # this could be your main company home page; for now, we just redirect to /kb
    (r'^index$|^index/$|^$', ekb.views.redirect),

    (r'^kb/(?P<id>\d+)(/.+)?\.pdf$',
     ekb.views.pdf),
    (r'^kb/(?P<search>[^/]*)(/.*)?$',
     ekb.views.show),

    # WARNING: for testing only, insecure!
    (r'(?P<path>^style/.*)$', 'django.views.static.serve',
     {'document_root': os.getcwd(), 'show_indexes': True}),
)
