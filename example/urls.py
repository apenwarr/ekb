from django.conf.urls.defaults import *
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    (r'^techjunkie/$', 'techjunkie.views.index'),
    (r'^techjunkie/index.html$', 'techjunkie.views.index'),
    (r'^techjunkie/style.html$', 'techjunkie.views.style'),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    #(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    
    # Uncomment the next line to enable the admin:
    (r'^admin/(.*)', admin.site.root),
    
    # WARNING: development only, insecure!
    (r'(style/.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
            
)
