from django.shortcuts import render_to_response
import re, datetime
from helpers import *
from kb.models import Doc, Tag

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

def show(req, search = None):
    qsearch = req.REQUEST.get('q')
    if not search:
	search = qsearch

    dict = {}
    dict['menuitems'] = [('/index/', 'Home'),
			 ('/kb/', 'Knowledgebase')]
    dict['page'] = '/kb/'

    doc = _try_get(Doc.objects, id=atoi(search))
    if doc:
	print req.path
	page = '/kb/%d' % doc.id
	dict['page'] = page
	dict['search'] = qsearch
	if qsearch:
	    dict['menuitems'].append(('/kb/%s' % qsearch, 'Search "%s"' % qsearch))
	dict['menuitems'].append((page, 'Article #%d' % doc.id))
	dict['title'] = doc.title
	dict['when'] = nicedate(datetime.datetime.now() - doc.last_modified)
	dict['tags'] = [tag.name for tag in doc.tags.all()]
	dict['text'] = doc.text
	return render_to_response('kb/view.html', dict)
    else:
	if not search: search = ''
	page = '/kb/%s' % search
	dict['page'] = page
	if search:
	    dict['menuitems'].append((page, 'Search "%s"' % search))
	dict['search'] = search
	if search:
	    dict['urlappend'] = '?q=%s' % search
	dict['title'] = 'Search: "%s"' % search

	f = Doc.objects.all()
	for word in search.split():
	    f = f & (Doc.objects.filter(title__icontains = word) |
		     Doc.objects.filter(text__icontains = word))
	dict['docs'] = f
		
	return render_to_response('kb/search.html', dict)
