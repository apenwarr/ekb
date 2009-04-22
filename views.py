from django.shortcuts import render_to_response
import re
from eql.kb.models import Doc, Tag
from helpers import *

dict = {'menuitems': [('/index/', 'Home'),
		      ('/kb/', 'Knowledgebase'),
		      ],
	};

def show(req, search=''):
    search = req.REQUEST.get('q', search)
    dict['page'] = '/kb/'
    dict['title'] = 'Search: "%s"' % search
    dict['tags'] = ['this','that','the other thing']
    dict['text'] = "Hey, I'm some text!"
    return render_to_response('kb/view.html', dict)
