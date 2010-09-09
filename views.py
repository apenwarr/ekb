from django.shortcuts import render_to_response
from django.http import HttpResponse, Http404, \
        HttpResponseRedirect, HttpResponsePermanentRedirect
from django.utils import html
from django.db import IntegrityError
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE
from os.path import dirname
import os, re, datetime, markdown, urllib
from ekb.models import Doc, db, autosummarize
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
    doc = Doc.try_get(id=docid)
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


def _alltags():
    return db.select('select tag,count(tag) '
                     '  from Tags '
                     '  group by tag '
                     '  order by tag ')


def _tagdocs(search):
    tag = None
    docs = []
    for t,d in db.run('select tag,docid from Tags where tag=?', search):
        tag = t
        docs.append(d)
    return tag,docs


def _marks(l):
    return ','.join(['?'] * len(l))


def show(req, search = None):
    urlexpander = lambda url: _html_url(req, url)
    qsearch = req.REQUEST.get('q', '')
    if not search:
        search = qsearch

    dict = {}
    dict['alltags'] = _alltags()
    dict['alldocs'] = Doc
    dict['menuitems'] = [
        ('/kb/', 'Knowledgebase'),
    ]

    doc = Doc.try_get(id=atoi(search))
    if doc: search = qsearch  # the old search was really a docid
    tag,tagdocs = _tagdocs(search)
    print 'tds: %r %r %r' % (search, tag, tagdocs)

    if search:
        dict['urlappend'] = '?q=%s' % search
    want_words = search.lower().split()

    if search:
        if tag:
            dict['menuitems'].append(('/kb/%s' % search, tag))
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
        if req.path != pagebase and req.path != urllib.unquote(pagebase):
            return HttpResponsePermanentRedirect(page)
        dict['page'] = page
        if not tag and not search and doc.tags:
            t = doc.tags[0]
            dict['menuitems'].append(('/kb/%s' % t, t))
        dict['menuitems'].append((page, 'KB%d' % doc.id))
        dict['title'] = doc.title
        dict['when'] = nicedate(doc.mtime)
        dict['tags'] = doc.tags
        dict['editurl'] = doc.get_edit_url()
        dict['pdfurl'] = doc.get_pdf_url()
        dict['text'] = h.highlight(doc.expanded_text(urlexpander,
                                                     headerdepth=3,
                                                     expandbooks=0),
                                   markdown.markdown)
        dict['reference_parents'] = list(doc.reference_parents())
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
            f = tagdocs
            dict['skip_tags'] = 1
            dict['title'] = 'Category: %s' % tag
            dict['search'] = ''
        elif search:
            # the search term is just a search term
            dict['title'] = 'Search: "%s"' % search
            words = []
            docids = list(db.selectcol('select docid from WordWeights '
                                       '  where word=?', want_words[0]))
            for word in want_words[1:]:
                if not docids:
                    # no remaining matches
                    break
                docids = list(db.selectcol('select docid from WordWeights '
                                           '  where word=? and docid in (%s)'
                                           % _marks(docids),
                                           word, *docids))
            l = want_words + docids
            docweights = db.select('select avg(weight)*count(weight), docid '
                                   '  from WordWeights '
                                   '  where word in (%s) and docid in (%s) '
                                   '  group by docid '
                                   % (_marks(want_words), _marks(docids)),
                                   *l)
            f = []
            for weight,docid in sorted(docweights):
                if weight > 0.0:
                    f.append(docid)
        else:
            # there is no search term; toplevel index
            dict['title'] = 'Knowledgebase'
            return render_to_response('ekb/kb.html', dict)

        dict['docs'] = []
        for docid in f:
            d = Doc(docid)
            d.autosummary = autosummarize(d.expanded_text(urlexpander,
                                                         headerdepth=1,
                                                         expandbooks=1),
                                          want_words, h.highlight)
            dict['docs'].append(d)
                
        return render_to_response('ekb/search.html', dict)


def edit(req, id, docname):
    docid = atoi(id)
    doc = Doc.try_get(id=docid)
    if not doc:
        raise Http404("Document #%d (%s) does not exist." % (docid, id))

    doc.use_latest()
    page = doc.get_edit_url()
        
    dict = {}
    dict['alltags'] = _alltags()
    dict['alldocs'] = Doc
    dict['menuitems'] = [
        ('/kb/', 'Knowledgebase'),
    ]
    if len(doc.tags) > 0:
        t = doc.tags[0]
        dict['menuitems'].append(('/kb/%s' % t, t))
    dict['menuitems'].append((doc.get_url(), 'KB%d' % doc.id))
    dict['menuitems'].append((doc.get_edit_url(), '-Edit-'))
    dict['page'] = page
    dict['title'] = doc.title
    dict['tags'] = join(', ', doc.tags)
    dict['uploadurl'] = doc.get_upload_url()
    dict['text'] = doc.text

    return render_to_response('ekb/edit.html', dict)

    
def _try_delete(doc):
    unlink('./%s' % doc.pathname)
    if os.path.isdir('docs/.git'):
        pn = './%s' % doc.pathname
        msg = 'kb: removed "%s" via web' % doc.filename
        p = Popen(args = ['git', 'rm', '--', pn], cwd = 'docs')
        p.wait()
        p = Popen(args = ['git', 'commit', '-m', msg], cwd = 'docs')
        p.wait()
    doc.delete()


def _try_save(doc, title, tags, text):
    mkdirp(os.path.dirname('docs/%s' % doc.pathname))
    f = open('docs/%s' % doc.pathname, 'w')
    f.write(("Title: %s\nTags: %s\n\n%s"
             % (title, tags, text)).replace('\r', '').encode('utf-8'))
    f.close()
    if os.path.isdir('docs/.git'):
        pn = './%s' % doc.pathname
        msg = 'kb: updated "%s" via web' % doc.filename
        p = Popen(args = ['git', 'add', '--', pn], cwd = 'docs')
        p.wait()
        p = Popen(args = ['git', 'commit', '-m', msg], cwd = 'docs')
        p.wait()
    doc.use_latest()
    doc.title = title
    doc.save()
    db.commit()


def save(req, id, docname):
    if not req.POST:
        return HttpResponse('Error: you must use POST to save pages.',
                            status=500)
    docid = atoi(id)
    doc = Doc.try_get(id=docid)
    if not doc:
        raise Http404("Document #%d (%s) does not exist." % (docid, id))
    title = req.REQUEST.get('title-text', 'Untitled').replace('\n', ' ')
    tags  = req.REQUEST.get('tags-text', '').replace('\n', ' ')
    text  = req.REQUEST.get('markdown-text', '').strip()
    redir_url = doc.get_url()  # this function is uncallable after delete()
    if not text:
        _try_delete(doc)
    else:
        xtitle = title
        di = 0
        while 1:
            if di > 1:
                xtitle = '%s [dup#%d]' % (title, di)
            elif di == 1:
                xtitle = '%s [dup]' % title
            try:
                _try_save(doc, xtitle, tags, text)
            except IntegrityError:
                if di < 16:
                    di += 1
                    continue
                else:
                    raise
            break
    return HttpResponseRedirect(redir_url)


def upload(req, id, docname):
    p = req.POST
    for f in req.FILES.values():
        if f.name.find(".") >= 0:
            (name, ext) = f.name.rsplit(".", 1)
            ext = ext.lower()
        else:
            name = f.name
            ext = ''
        if ext in ['jpg', 'gif', 'png']:
            nicename = re.sub(r'[^\w]', '-', name)
            tryname = "%s.%s" % (nicename, ext)
            i = 0
            while os.path.exists("static/kbfiles/%s" % tryname):
                i += 1
                tryname = "%s-%d.%s" % (nicename, i, ext)
            outf = open("static/kbfiles/%s" % tryname, "w")
            for c in f.chunks():
                outf.write(c)
            outf.close()
            return HttpResponse("0 %s" % tryname)
        else:
            return HttpResponse(
                  "1 You can only upload .gif, .png, or .jpg files.")
    return HttpResponse("Error", status=400)
