from django.conf.urls.defaults import *
import os

urlpatterns = patterns('',
    # this could be your main company home page; for now, we just redirect to /kb
    (r'^index$|^index/$|^$', 
     'ekb.views.redirect'),

    # comment out these if you want to disable page editing
    (r'^kb/(?P<id>\d+)(?P<docname>/.+)/edit$',
     'ekb.views.edit'),
    (r'^kb/0/(?P<docname>[-_A-Za-z0-9 ]+)/new$',
     'ekb.views.new'),
    (r'^kb/(?P<id>\d+)(?P<docname>/[-\'_A-Za-z0-9 ]+)/save$',
     'ekb.views.save'),
    (r'^kb/upload$',
     'ekb.views.upload'),

    # comment out this one if you want to disable pdf rendering via pandoc/latex
    (r'^kb/(?P<id>\d+)(?P<docname>/.+)?\.pdf$',
     'ekb.views.pdf'),

    # you're going to need these ones if you want to search/view pages
    (r'^kb/(?P<search>\d*)(/.*)?$',
     'ekb.views.show'),
    (r'^kb/(?P<search>.+)$',
     'ekb.views.show'),

    # WARNING: for testing only, insecure!
    (r'(?P<path>^static/.*)$', 'django.views.static.serve',
     {'document_root': os.getcwd(), 'show_indexes': True}),
)
