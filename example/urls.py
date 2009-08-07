from django.conf.urls.defaults import *
import os

urlpatterns = patterns('',
    # this could be your main company home page; for now, we just redirect to /kb
    (r'^index$|^index/$|^$', 
     'ekb.views.redirect'),

    (r'^kb/(?P<id>\d+)(?P<docname>/.+)/edit$',
     'ekb.views.edit'),
    (r'^kb/(?P<id>\d+)(?P<docname>/.+)/save$',
     'ekb.views.save'),
    (r'^kb/(?P<id>\d+)(?P<docname>/.+)?\.pdf$',
     'ekb.views.pdf'),
    (r'^kb/(?P<search>[^/]*)(?P<docname>/.*)?$',
     'ekb.views.show'),

    # WARNING: for testing only, insecure!
    (r'(?P<path>^static/.*)$', 'django.views.static.serve',
     {'document_root': os.getcwd(), 'show_indexes': True}),
)
