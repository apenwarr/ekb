from django.shortcuts import render_to_response
from django.http import HttpResponse, Http404, \
	HttpResponseRedirect, HttpResponsePermanentRedirect
from django.utils import html
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE
from os.path import dirname
import os, re, datetime, markdown
from ekb.models import Doc, Tag, Word
from PIL import Image
from handy import atoi, join, nicedate, pluralize, mkdirp, unlink

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
    text = re.sub(r'[*`]', '', text)
    text = re.sub(re.compile(r'^(\s*- |\s*\d+\. |\s*>+ )', re.M), ' ', text)
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

def _subfile(req, filename, doc):
    t = open(filename).read().decode('utf-8')
    t = re.sub('%id%', req.build_absolute_uri(doc.get_url_basic()), t)
    t = re.sub('%title%', doc.title, t)
    return t.encode('utf-8')

def _texfix(req, doc, t):
    footer = _subfile(req, "ekb/latex.footer", doc)
    if re.search(re.compile(r'^\\subsection', re.M), t):
	# lots of subsections: must be a book
	header = _subfile(req, "ekb/latex.book", doc)
	t = re.sub(re.compile(r'^\\section', re.M), 
		   r'\chapter', t)
	t = re.sub(re.compile(r'^\\subsection', re.M), 
		   r'\section', t)
	t = re.sub(re.compile(r'^\\subsubsection', re.M), 
		   r'\subsection', t)
	t = re.sub(re.compile(r'^\\subsubsubsection', re.M), 
		   r'\subsubsection', t)
    else:
	header = _subfile(req, "ekb/latex.article", doc)
    return header + t + footer

def _html_url(req, name):
    # return req.build_absolute_uri(name)
    return name
    #return 'fruit'

def _pdf_url(req, name):
    if name.startswith("/static/kbfiles/"):
	name = os.getcwd() + name
	dir = os.path.dirname(name)
	base = os.path.basename(name)
	if not os.path.exists(name):
	    return "invalid-path"
	if base.endswith(".gif"):
	    # pdflatex can't handle .gif files, sigh
	    outdir = os.path.join(dir, ".convert")
	    pngname = os.path.join(outdir, base[:-4] + '.png')
	    if not os.path.exists(pngname) \
	            or os.path.getmtime(name) >= os.path.getmtime(pngname):
		mkdirp(outdir)
		unlink(pngname)
		im = Image.open(name)
		im.save(pngname, "PNG")
	    return pngname
	else:
	    return name
    else:
	return req.build_absolute_uri(name)

def pdf(req, id, docname):
    urlexpander = lambda url: _pdf_url(req, url)
    docid = atoi(id)
    doc = _try_get(Doc.objects, id=docid)
    if not doc:
	raise Http404("Document #%d (%s) does not exist." % (docid, id))
    else:
	mdfx = NamedTemporaryFile()
	name = mdfx.name

	mdfname = name + '.mdown'
	mdf = open(mdfname, 'w')
	mdf.write(doc.expanded_text(urlexpander, headerdepth=1, expandbooks=1)
		  .encode('utf-8'))
	mdf.flush()

	p = Popen(args = ['pandoc',
			  '-f', 'markdown',
			  '-t', 'latex',
			  mdfname],
		  stdout=PIPE)
	latex = p.stdout.read()
	latex = re.sub(r'\\includegraphics{(.*?)}',
		       r'\\resizebox{4in}{!}{\\includegraphics{\1}}',
		       latex)
	p.wait()
	
	ltname = name + '.latex'
	pdname = name + '.pdf'
	ltf = open(ltname, 'w')
	ltf.write(_texfix(req, doc, latex))
	ltf.flush()
	p.wait()
	#mdf.close()
	print 'Latex file: %s' % ltname
	for d in [1,2]:
	    # we have to do this twice so that the TOC is generated correctly
	    p = Popen(args = ['pdflatex', '-interaction', 'batchmode', ltname],
		      cwd = dirname(ltname))
	    p.wait()
	pd = open(pdname)
	#os.unlink(pdname)
	#os.unlink(ltname)
	return HttpResponse(pd, "application/pdf")

def show(req, search = None, docname = None):
    urlexpander = lambda url: _html_url(req, url)
    qsearch = req.REQUEST.get('q', '')
    if not search:
	search = qsearch

    dict = {}
    dict['alltags'] = Tag.objects.order_by('name')
    dict['alldocs'] = Doc.objects
    dict['menuitems'] = [
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
	doc.use_latest()
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
	dict['when'] = nicedate(doc.last_modified)
	dict['tags'] = doc.tags.all()
	dict['editurl'] = doc.get_edit_url()
	dict['pdfurl'] = doc.get_pdf_url()
	dict['text'] = h.highlight(doc.expanded_text(urlexpander,
						     headerdepth=3,
						     expandbooks=0),
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
	    d.autosummary = _autosummary(d.expanded_text(urlexpander,
							 headerdepth=1,
							 expandbooks=1),
					 want_words, h)
	    dict['docs'].append(d)
		
	return render_to_response('ekb/search.html', dict)

def edit(req, id, docname):
    docid = atoi(id)
    doc = _try_get(Doc.objects, id=docid)
    if not doc:
	raise Http404("Document #%d (%s) does not exist." % (docid, id))

    doc.use_latest()
    page = doc.get_edit_url()
	
    dict = {}
    dict['alltags'] = Tag.objects.order_by('name')
    dict['alldocs'] = Doc.objects
    dict['menuitems'] = [
	('/kb/', 'Knowledgebase'),
    ]
    if len(doc.tags.all()) > 0:
	t = doc.tags.all()[0]
	dict['menuitems'].append(('/kb/%s' % t.name, t.name))
    dict['menuitems'].append((doc.get_url(), 'KB%d' % doc.id))
    dict['menuitems'].append((doc.get_edit_url(), '-Edit-'))
    dict['page'] = page
    dict['title'] = doc.title
    dict['tags'] = join(', ', [t.name for t in doc.tags.all()])
    dict['text'] = doc.text()

    return render_to_response('ekb/edit.html', dict)

def save(req, id, docname):
    docid = atoi(id)
    doc = _try_get(Doc.objects, id=docid)
    if not doc:
	raise Http404("Document #%d (%s) does not exist." % (docid, id))
    title = req.REQUEST.get('title-text', 'Untitled').replace('\n', ' ')
    tags  = req.REQUEST.get('tags-text', '').replace('\n', ' ')
    text  = req.REQUEST.get('markdown-text', '')
    if text:
	f = open('docs/%s' % doc.filename, 'w')
	f.write(("Title: %s\nTags: %s\n\n%s"
		 % (title, tags, text)).encode('utf-8'))
    return HttpResponseRedirect(doc.get_url())
