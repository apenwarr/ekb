from django.shortcuts import render_to_response
import re, datetime, markdown
from helpers import *
from kb.models import Doc, Tag

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

_default_highlighter = HtmlHighlighter('', 'strong')

def show(req, search = None):
    qsearch = req.REQUEST.get('q')
    if not search:
	search = qsearch

    dict = {}
    dict['menuitems'] = [('/index/', 'Home'),
			 ('/kb/', 'Knowledgebase')]

    dict['alltags'] = Tag.objects.all()
    dict['alldocs'] = Doc.objects.all()
    
    doc = _try_get(Doc.objects, id=atoi(search))
    if doc:
	print req.path
	page = '/kb/%d' % doc.id
	dict['page'] = page
	dict['search'] = qsearch
	h = _default_highlighter
	if qsearch:
	    dict['menuitems'].append(('/kb/%s' % qsearch, '"%s"' % qsearch))
	    h = HtmlHighlighter(qsearch.split(), 'strong')
	dict['menuitems'].append((page, 'Article #%d' % doc.id))
	dict['title'] = doc.title
	dict['when'] = nicedate(datetime.datetime.now() - doc.last_modified)
	dict['tags'] = doc.tags.all()
	dict['text'] = h.highlight(doc.text, markdown.markdown)
	return render_to_response('kb/view.html', dict)
    else:
	if not search:
	    search = ''
	page = '/kb/%s' % search
	dict['page'] = page
	if search:
	    dict['menuitems'].append((page, 'Search'))
	dict['search'] = search
	if search:
	    dict['urlappend'] = '?q=%s' % search
	dict['title'] = 'Search: "%s"' % search

	tag = _try_get(Tag.objects, name__iexact=search)
	if tag:
	    f = tag.doc_set.all()
	else:
	    f = Doc.objects.all()
	    for word in search.split():
		f = f & (Doc.objects.filter(title__icontains = word) |
			 Doc.objects.filter(text__icontains = word))
	dict['docs'] = f
		
	return render_to_response('kb/search.html', dict)
