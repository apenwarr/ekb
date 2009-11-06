from django.conf.urls.defaults import *
import os

urlpatterns = patterns('',
    # this could be your main company home page; for now, we just redirect to /kb
    (r'^index$|^index/$|^$', 
     'ekb.views.redirect'),

    # comment out these if you want to disable page editing
    (r'^kb/(?P<id>\d+)(?P<docname>/[^/]+)/edit$',
     'ekb.views.edit'),
    (r'^kb/(?P<id>\d+)(?P<docname>/[^/]+)/save$',
     'ekb.views.save'),
    (r'^kb/(?P<id>\d+)(?P<docname>/[^/]+)/upload$',
     'ekb.views.upload'),

    # comment out this one if you want to disable pdf rendering via pandoc/latex
    (r'^kb/(?P<id>\d+)(?P<docname>/.+)?\.pdf$',
     'ekb.views.pdf'),

    # you're going to need this one if you want to search/view pages
    (r'^kb/(?P<search>[^/]*)(?P<docname>/[^/]*)?$',
     'ekb.views.show'),

    # WARNING: for testing only, insecure!
    (r'(?P<path>^static/.*)$', 'django.views.static.serve',
     {'document_root': os.getcwd(), 'show_indexes': True}),
)
