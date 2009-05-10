from django.shortcuts import render_to_response
from django.http import HttpResponse, Http404, \
	HttpResponseRedirect, HttpResponsePermanentRedirect
from django.utils import html
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE
from os.path import dirname
import os, re, datetime, markdown
from ekb.models import Doc, Tag, Word
from handy import atoi, join, nicedate, pluralize

class HtmlHighlighter:
    def __init__(self, want_words, highlight_tag):
	self.wordsub = None
	self.wordfix = None
	self.replacement = None

	want_esc = join("|", [re.escape(x) for x in want_words])
	if want_esc and highlight_tag:
	    self.wordsub = re.compile('(' + want_esc + ')', re.I)
	    htag = re.sub(r'\W', '_', highlight_tag)
	    self.wordfix = re.compile('&lt;%s&gt;(.*?)&lt;/%s&gt;' % (htag, htag))
	    self.replacement = u'<%s>\\1</%s>' % (htag, htag)
	
    def highlight(self, s, process = html.escape):
	if s is None:
	    return ''
	else:
	    s = unicode(s)
	if self.wordsub and self.replacement:
	    s = re.sub(self.wordsub, self.replacement, s)
	s = process(unicode(s))
	if self.wordsub and self.replacement:
	    s = re.sub(self.wordfix, self.replacement, s)
	return s
	
def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

def _fixheader(s, lastc):
    if lastc.isalnum():
	return s+lastc+':'
    else:
	return s+lastc

def _autosummary(text, want_words, highlighter, width = 120):
    # sort words from least to most common; the blurb should show the most
    # interesting word if possible
    sortwords = [w.name for w in 
		 Word.objects.filter(name__in = want_words).order_by('total')]

    # get rid of some markdown cruft
    text = re.sub(re.compile('^#+(.*)(\S)\s*$', re.M),
		  lambda m: _fixheader(m.group(1), m.group(2)),
		  text)
    text = re.sub(r'\[(.*?)\]\s*\[.*?\]', r'\1', text)
    text = re.sub(r'\[(.*?)\]\s*\(.*?\)', r'\1', text)
    text = re.sub(r'[*`]', ' ', text)
    text = " %s " % text
    
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
	text = text[start:]
	hi = ''
    else:
	while end >= 0 and not text[end].isalnum():
	    end -= 1
	while end < len(text) and text[end].isalnum():
	    end += 1
	text = text[start:end]
	hi = "<b>...</b>"

    return highlighter.highlight(text, html.escape) + hi

def redirect(req):
    return HttpResponseRedirect('/kb/')

def pdf(req, id):
    docid = atoi(id)
    doc = _try_get(Doc.objects, id=docid)
    if not doc:
	raise Http404("Document #%d (%s) does not exist." % (docid, id))
    else:
	mdf = NamedTemporaryFile()
	mdf.write(doc.expanded_text().encode('utf-8'))
	mdf.flush()

	p = Popen(args = ['pandoc',
			  '-f', 'markdown',
			  '-t', 'latex',
			  mdf.name],
		  stdout=PIPE)
	ltname = mdf.name + '.latex'
	pdname = mdf.name + '.pdf'
	ltf = open(ltname, 'w')
	ltf.write(open("ekb/latex.header").read())
	ltf.write(p.stdout.read())
	ltf.write(open("ekb/latex.footer").read())
	ltf.flush()
	p.wait()
	mdf.close()
	p = Popen(args = ['pdflatex', '-interaction', 'batchmode', ltname],
		  cwd = dirname(ltname))
	p.wait()
	pd = open(pdname)
	os.unlink(pdname)
	os.unlink(ltname)
	return HttpResponse(pd, "application/pdf")

def show(req, search = None):
    qsearch = req.REQUEST.get('q', '')
    if not search:
	search = qsearch

    dict = {}
    dict['alltags'] = Tag.objects.order_by('name')
    dict['alldocs'] = Doc.objects
    dict['menuitems'] = [
#	('/index/', 'Home'),
	('/kb/', 'Knowledgebase'),
    ]

    doc = _try_get(Doc.objects, id=atoi(search))
    if doc: search = qsearch  # the old search was really a docid
    tag = _try_get(Tag.objects, name__iexact=search)

    if search:
	dict['urlappend'] = '?q=%s' % search
    want_words = search.lower().split()

    if search:
	if tag:
	    dict['menuitems'].append(('/kb/%s' % search, tag.name))
	else:
	    dict['menuitems'].append(('/kb/%s' % search, '"%s"' % search))

    if tag:
	h = HtmlHighlighter([], '')
    else:
	h = HtmlHighlighter(want_words, 'u')

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
	return render_to_response('ekb/view.html', dict)
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
		    # we know every word is in every remaining doc
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
	    return render_to_response('ekb/kb.html', dict)

	dict['docs'] = []
	for d in f:
	    d.autosummary = _autosummary(d.expanded_text(), want_words, h)
	    dict['docs'].append(d)
		
	return render_to_response('ekb/search.html', dict)
