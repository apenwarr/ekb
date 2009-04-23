from django.shortcuts import render_to_response
import re, datetime, markdown
from helpers import *
from kb.models import Doc, Tag

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

def _autosummary(text, want_words, highlighter, width = 160):
    text = " " + text + " "
    match = matchend = -1
    for w in want_words:
	match = text.lower().find(w.lower())
	if match >= 0:
	    matchend = match + len(w)
	    break
    if match < 0:
	match = 0

    start = max(text[:match].rfind(".") + 1,
		text[:match].rfind("!") + 1)
    if matchend-start >= width:
	start = matchend-width/2

    while start < len(text) and not text[start].isspace():
	start += 1
    end = start + width
    if end >= len(text):
	end = len(text)-1
    while end >= 0 and not text[end].isalnum():
	end -= 1
    while end < len(text) and text[end].isalnum():
	end += 1

    return highlighter.highlight(text[start:end], html.escape) + "<b>...</b>"

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
	h = HtmlHighlighter(qsearch.split(), 'strong')
	if qsearch:
	    dict['menuitems'].append(('/kb/%s' % qsearch, '"%s"' % qsearch))
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
	h = HtmlHighlighter(search.split(), 'strong')
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

	want_words = search.split()
	dict['docs'] = []
	for d in f:
	    d.autosummary = _autosummary(d.text, want_words, h)
	    dict['docs'].append(d)
		
	return render_to_response('kb/search.html', dict)
