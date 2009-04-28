from django.shortcuts import render_to_response
from django.http import HttpResponsePermanentRedirect
import re, datetime, markdown
from helpers import *
from kb.models import Doc, Tag, Word

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

def _autosummary(text, want_words, highlighter, width = 120):
    # sort words from least to most common; the blurb should show the most
    # interesting word if possible
    sortwords = [w.name for w in 
		 Word.objects.filter(name__in = want_words).order_by('total')]
    print sortwords
    
    text = " " + re.sub('#+', '', text) + " "
    match = matchend = -1
    for w in sortwords:
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
    dict['alltags'] = Tag.objects.order_by('name')
    dict['alldocs'] = Doc.objects
    dict['menuitems'] = [('/index/', 'Home'),
			 ('/kb/', 'Knowledgebase')]

    doc = _try_get(Doc.objects, id=atoi(search))
    if doc: search = qsearch  # the old search was really a docid
    tag = _try_get(Tag.objects, name__iexact=search)

    if search:
	dict['urlappend'] = '?q=%s' % search
    want_words = search.lower().split()
    h = HtmlHighlighter(want_words, 'strong')

    if search:
	if tag:
	    dict['menuitems'].append(('/kb/%s' % search, tag.name))
	else:
	    dict['menuitems'].append(('/kb/%s' % search, '"%s"' % search))

    dict['search'] = search
	
    if doc:
	# View the specific article they requested.
	pagebase = doc.get_url()
	page = pagebase + dict.get('urlappend', '')
	if req.path != pagebase:
	    return HttpResponsePermanentRedirect(page)
	dict['page'] = page
	if not tag and not search and len(doc.tags.all()) > 0:
	    t = doc.tags.all()[0]
	    dict['menuitems'].append(('/kb/%s' % t.name, t.name))
	dict['menuitems'].append((page, 'KB%d' % doc.id))
	dict['title'] = doc.title
	dict['when'] = nicedate(datetime.datetime.now() - doc.last_modified)
	dict['tags'] = doc.tags.all()
	dict['text'] = h.highlight(doc.expanded_text(headerdepth=3),
				   markdown.markdown)
	dict['similar'] = doc.similar(max=4)
	dict['dissimilar'] = doc.dissimilar(max=4)
	if tag:
	    dict['search'] = ''
	return render_to_response('kb/view.html', dict)
    else:
	# Search for matching articles
	page = '/kb/%s' % search
	dict['page'] = page

	if tag:
	    # the search term is actually the name of a tag
	    f = tag.doc_set.order_by('title')
	    dict['skip_tags'] = 1
	    dict['title'] = 'Category: %s' % tag.name
	    dict['search'] = ''
	elif search:
	    # the search term is just a search term
	    dict['title'] = 'Search: "%s"' % search
	    docs = Doc.objects.all()
	    docweights = {}
	    words = []
	    for word in want_words:
		w = _try_get(Word.objects, name=word)
		if not w:
		    # word isn't in any doc, so empty search results
		    docs = []
		    break
		words.append(w)
		docs = docs & w.doc_set.all()
	    for doc in docs:
		weight = 1.0
		for word in words:
		    # we know this every word is in every remaining doc
		    weight *= doc.wordweight_set.get(word=w).weight
		docweights[doc] = weight
	    f = []
	    for doc,weight in sorted(docweights.items(),
				     lambda x,y: cmp(y[1],x[1])):
		if weight > 0.0:
		    f.append(doc)
	else:
	    # there is no search term; toplevel index
	    dict['title'] = 'Knowledgebase'
	    return render_to_response('kb/kb.html', dict)

	dict['docs'] = []
	for d in f:
	    d.autosummary = _autosummary(d.expanded_text(), want_words, h)
	    dict['docs'].append(d)
		
	return render_to_response('kb/search.html', dict)
