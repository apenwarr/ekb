from django.shortcuts import render_to_response
import re, datetime, markdown
from helpers import *
from kb.models import Doc, Tag

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

def _autosummary(text, want_words, highlighter, width = 120):
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
    qsearch = req.REQUEST.get('q', '')
    if not search:
	search = qsearch

    dict = {}
    dict['alltags'] = Tag.objects
    dict['alldocs'] = Doc.objects
    dict['menuitems'] = [('/index/', 'Home'),
			 ('/kb/', 'Knowledgebase')]

    doc = _try_get(Doc.objects, id=atoi(search))
    if doc: search = qsearch  # the old search was really a docid
    tag = _try_get(Tag.objects, name__iexact=search)

    dict['search'] = search
    if search:
	dict['urlappend'] = '?q=%s' % search
    want_words = search.split()
    h = HtmlHighlighter(want_words, 'strong')

    if search:
	if tag:
	    dict['menuitems'].append(('/kb/%s' % search, tag.name))
	else:
	    dict['menuitems'].append(('/kb/%s' % search, '"%s"' % search))
	
    if doc:
	# View the specific article they requested.
	page = '/kb/%d%s' % (doc.id, dict.get('urlappend', ''))
	dict['page'] = page
	dict['menuitems'].append((page, 'Article #%d' % doc.id))
	dict['title'] = doc.title
	dict['when'] = nicedate(datetime.datetime.now() - doc.last_modified)
	dict['tags'] = doc.tags.all()
	dict['text'] = h.highlight(doc.text, markdown.markdown)
	return render_to_response('kb/view.html', dict)
    else:
	# Search for matching articles
	page = '/kb/%s' % search
	dict['page'] = page

	if tag:
	    # the search term is actually the name of a tag
	    f = tag.doc_set.all()
	    dict['skip_tags'] = 1
	    dict['title'] = 'Category: %s' % tag.name
	elif search:
	    # the search term is just a search term
	    dict['title'] = 'Search: "%s"' % search
	    f = Doc.objects.all()
	    for word in want_words:
		f = f & (Doc.objects.filter(title__icontains = word) |
			 Doc.objects.filter(text__icontains = word))
	else:
	    # there is no search term; toplevel index
	    dict['title'] = 'Knowledgebase'
	    dict['message'] = 'Please choose a category or enter a search term.'
	    f = []

	dict['docs'] = []
	for d in f:
	    d.autosummary = _autosummary(d.text, want_words, h)
	    dict['docs'].append(d)
		
	return render_to_response('kb/search.html', dict)
