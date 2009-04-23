from django.shortcuts import render_to_response
import re, datetime
from helpers import *
from kb.models import Doc, Tag

_dict = {'menuitems': [('/index/', 'Home'),
		      ('/kb/', 'Knowledgebase'),
		      ],
	};

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

def show(req, search=''):
    search = req.REQUEST.get('q', search)

    dict = {}
    dict.update(_dict)
    dict['page'] = '/kb/'

    doc = _try_get(Doc.objects, id=atoi(search))
    if doc:
	dict['title'] = doc.title
	dict['when'] = nicedate(datetime.datetime.now() - doc.last_modified)
	dict['tags'] = [tag.name for tag in doc.tags.all()]
	dict['text'] = doc.text
	return render_to_response('kb/view.html', dict)
    else:
	dict['title'] = 'Search: "%s"' % search
	dict['when'] = '5 days ago'
	dict['tags'] = ['this','that','the other thing']
	dict['text'] = "Hey, I'm some text!"
	dict['search'] = search
	return render_to_response('kb/view.html', dict)

