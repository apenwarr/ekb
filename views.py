from django.shortcuts import render_to_response
import re
from helpers import *
from kb.models import Doc, Tag

dict = {'menuitems': [('/index/', 'Home'),
		      ('/kb/', 'Knowledgebase'),
		      ],
	};

def show(req, search=''):
    search = req.REQUEST.get('q', search)
    dict['page'] = '/kb/'
    dict['title'] = 'Search: "%s"' % search
    dict['when'] = '5 days ago'
    dict['tags'] = ['this','that','the other thing']
    dict['text'] = "Hey, I'm some text!"
    return render_to_response('kb/view.html', dict)
