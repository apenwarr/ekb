import re, os, datetime, sqlite3
from settings import DEBUG
from django.db import models
from django.core.urlresolvers import NoReverseMatch
from django.utils import html
import sss
from helpers import *

def _create_v1(db):
    db.run('create table Docs '
           '    (id primary key, filename, pathname, title, mtime)')
    
    db.run('create table Refs '
           '    (from_doc, to_doc)')
    db.run('create unique index Refs_pk on Refs (from_doc, to_doc)')
    
    db.run('create table Tags '
           '    (docid, tag)')
    db.run('create unique index Tags_pk on Tags (docid, tag)')
    db.run('create index Tags_tag on Tags (tag)')
    
    db.run('create table RelatedDocs '
           '    (from_doc, to_doc, weight)')
    db.run('create unique index RelatedDocs_pk on RelatedDocs '
           '    (from_doc, to_doc)')
    
    db.run('create table Words '
           '    (word, total)')
    db.run('create unique index Words_pk on Words (word)')

    db.run('create table WordWeights '
           '    (docid, word, weight)')
    db.run('create unique index WordWeights_pk on WordWeights '
           '    (docid, word)')
    
_schema = [(1, _create_v1)]


class EkbDb(sss.Db):
    def __init__(self):
        sss.Db.__init__(self, 'ekb.db', _schema)

db = EkbDb()


def parse_doc(topdir, dirfile):
    fullpath = topdir + dirfile
    tags = os.path.dirname(dirfile).split("/")
    title = os.path.basename(dirfile)

    if not os.path.exists(fullpath):
        return (title, filter(None, tags), None, '(Deleted)')
    f = open(fullpath)
    line = f.readline()
    while line and line.strip():
        (k,v) = line.split(":", 1)
        if k.lower() == 'title':
            title = v.strip()
        elif k.lower() == 'tags':
            for t in v.split(','):
                if not t in tags:
                    tags.append(t.strip())
        else:
            raise KeyError('Unknown header: "%s"' % k)
        line = f.readline()
    tags = filter(None, tags)
    mtime = os.stat(fullpath).st_mtime
    return (title, list(set(tags)), mtime, f.read().decode('utf-8'))


def parse_refs(text):
    # find everything of the form [xyz] or [[xyz]] or [include:xyz] etc.
    refs = re.findall(r'\[([^\[\]]+)\]', text)
    return [re.sub(r'^.*:', '', r) for r in refs]


def _fixheader(s, lastc):
    if lastc.isalnum():
        return s + lastc + ':'
    else:
        return s + lastc


def autosummarize(text, want_words = [], highlighter = None, width = 120):
    # sort words from least to most common; the blurb should show the most
    # interesting word if possible
    sortwords = list(db.selectcol('select word from Words where word in (%s) '
                                  '  order by total desc' 
                                  % (','.join(['?']*len(want_words))),
                                  *want_words))

    # get rid of some markdown cruft
    text = re.sub(re.compile('^#+(.*)(\S)\s*$', re.M),  # headings
                  lambda m: _fixheader(m.group(1), m.group(2)),
                  text)
    text = re.sub(r'\!\[(.*?)\]\s*\(.*?\)', r'', text)  # ![alt](url)
    text = re.sub(r'\[(.*?)\]\s*\[.*?\]', r'\1', text)  # [alt][url]
    text = re.sub(r'\[(.*?)\]\s*\(.*?\)', r'\1', text)  # [alt](url)
    text = re.sub(r'[*`]', '', text)
    text = re.sub(re.compile(r'^(\s*- |\s*\d+\. |\s*>+ )', # bullets
                             re.M), ' ', text)
    text = re.sub(re.compile(r'<(\S+)[^>]+>.*</\1>',
                             re.S + re.I), '', text) # html tags
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

    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    if highlighter:
        return highlighter(text, html.escape) + hi
    else:
        return text + hi


_includes_in_progress = {}
class Doc(object):
    def __init__(self, id):
        self.id = id
        (self.filename, self.pathname, self.title, self.mtime) = db.selectrow(
            'select filename, pathname, title, mtime '
            '  from Docs where id=?', id)
        self._text = None  # don't read by default
        self.tags = list(db.selectcol('select tag from Tags where docid=?', id))
        self.related = list(db.run('select weight,to_doc from RelatedDocs '
                                   '  where from_doc=?', id))
        self.references_to = list(db.selectcol('select to_doc from Refs '
                                               '  where from_doc=?', id))

    def save(self):
        db.run('insert or replace into Docs '
               '  (id, filename, pathname, title, mtime) '
               '  values (?,?,?,?,?)', self.id, self.filename, self.pathname,
               self.title, self.mtime)
        db.run('delete from Tags where docid=?', self.id)
        for t in self.tags:
            db.run('insert into Tags (docid, tag) values (?,?)',
                   self.id, t)
        db.run('delete from Refs where from_doc=?', self.id)
        for r in self.references_to:
            db.run('insert into Refs (from_doc, to_doc) '
                   '  values (?,?)', self.id, r)

    def delete(self):
        db.run('delete from Docs where id=?', self.id)

    @staticmethod
    def search(**kwargs):
        where = '1=1'
        args = []
        for k,v in kwargs.items():
            where += ' and %s=?' % k
            args.append(v)
        for i in db.selectcol('select id from Docs where %s' % where, *args):
            yield Doc(i)

    @staticmethod
    def try_get(**kwargs):
        for i in Doc.search(**kwargs):
            return i  # return the first match
        return None # no match

    @models.permalink
    def get_url(self):
        return ('ekb.views.show', 
                [self.id, 
                 "/" + re.sub(r"\..*$", "", self.filename)])
                
    @models.permalink
    def _get_pdf_url(self):
        return ('ekb.views.pdf', 
                [self.id, 
                 "/" + re.sub(r"\..*$", "", self.filename)])

    def get_pdf_url(self):
        try:
            return self._get_pdf_url()
        except NoReverseMatch:
            return None
                
    @models.permalink
    def _get_edit_url(self):
        return ('ekb.views.edit',
                [self.id, 
                 "/" + re.sub(r"\..*$", "", self.filename)])

    def get_edit_url(self):
        try:
            return self._get_edit_url()
        except NoReverseMatch:
            return None
                
    @models.permalink
    def _get_upload_url(self):
        return ('ekb.views.upload',
                [self.id, 
                 "/" + re.sub(r"\..*$", "", self.filename)])

    def get_upload_url(self):
        try:
            return self._get_upload_url()
        except NoReverseMatch:
            return None
                
    @models.permalink
    def get_url_basic(self):
        return ('ekb.views.show', [self.id])

    def read_latest(self):
        (self.title, self.tags, self.last_modified, self._text) \
                = parse_doc('docs', self.pathname)

    def use_latest(self):
        oldtags = self.tags
        if not self._text:
            self.read_latest()
        refs_names = parse_refs(self._text)
        self.references_to = []
        for name in set(refs_names):
            id = db.selectcell('select id from Docs where filename=?', name)
            if id:
                self.references_to.append(id)

    def _try_include(self, indent, filename, isfaq, skipto, expandbooks):
        indent = indent and int(indent) or 0
        d = Doc.try_get(filename=str(filename))
        if filename in _includes_in_progress:
            return '[[aborted-recursive-include:%s]]' % filename
        elif not d:
            return '[[missing-include:%s]]' % filename
        else:
            _includes_in_progress[filename] = 1
            t = self._process_includes(d.text, depth=indent+1,
                                       expandbooks=expandbooks)
            if isfaq:
                parts = re.split(re.compile(r'^#+.*$', re.M), t, 2)
                assert(len(parts) == 3)
                t = "%s %s\n\n%s\n\n" % ('#'*(indent+1),
                                         re.sub('\n', ' ', parts[1].strip()),
                                         parts[2].strip())
            elif skipto:
                t = re.sub(re.compile(r'.*^#+\s*%s$' % skipto,
                                      re.M+re.S),
                           '', t)
            del _includes_in_progress[filename]
            return t

    def _expand_book(self, do_expand, pounds, text, ref, skipto):
        if do_expand:
            return ("%s %s\n\n[[include+%d:%s%s]]\n\n"
                    % (pounds, text, len(pounds), ref,
                       skipto and "#"+skipto or ""))
        else:
            d = Doc.try_get(filename=str(ref))
            if d:
                summary = autosummarize(d.expanded_text(lambda x: x,
                                                        headerdepth=1,
                                                        expandbooks=1),
                                        width=200)
            else:
                summary = ''
            return ("%s [%s][%s]\n%s [(Read more)][%s]\n\n"
                    % (pounds, text, ref, summary, ref))

    def _process_includes(self, t, depth, expandbooks):
        # handle headers containing references.  We might want to turn them
        # into a normal header followed by an "include" (which we handle next)
        #
        # Format:  ### [This is a title][doc-file-name]
        #
        # or to drop everything before the 'Answer' section in the linked
        # article:
        #          ### [This is a title][doc-file-name#Answer]
        #
        t = re.sub(re.compile(r'^(#+)\s*\[([^]]*)\]\s*\[([^]#]*)(#([^]]*))?\]\s*$',
                              re.M),
                   lambda m: self._expand_book(expandbooks,
                                               m.group(1), m.group(2),
                                               m.group(3), m.group(5)),
                   t)
        
        # handle "include" references.  These are our own creation (not
        # standard markdown), of one of these forms:
        #      [[include:filename]]
        #      [[include+n:filename]]
        #      [[faqinclude+n:filename]]
        #      [[include:filename#Section Name]]
        # We just replace that text with the verbatim contents of the referred
        # document.
        t = re.sub(r'\[\[(faq)?include(\+(\d+))?:([^]#]*)(#([^]]*))?\]\]',
                   lambda m: self._try_include(m.group(3), m.group(4),
                                               m.group(1) == 'faq',
                                               m.group(6), expandbooks),
                   t)

        # normalize the headers: the toplevel header should be h1, no matter
        # what it is in the document itself.
        allheaders = re.findall(re.compile('^(#+)', re.M), t)
        minheader = min([99] + [len(h) for h in allheaders])
        return re.sub(re.compile(r'^' + '#'*minheader, re.M), '#'*depth, t)

    @property
    def text(self):
        if not self._text:
            self.read_latest()
        return self._text

    def expanded_text(self, urlexpander, headerdepth, expandbooks):
        text = self._process_includes(self.text, depth=headerdepth,
                                      expandbooks=expandbooks)

        # find all markdown 'refs' that refer to kb pages.
        # Markdown refs are of the form: [Description String] [refname]
        #
        # And we need to add a line like:
        #   [refname]: /the/path
        # to the bottom in order to make the ref resolvable.
        refs = re.findall(r'\[[^]]*\]\s*\[([^]]*)\]', text)
        for ref in refs:
            d = Doc.try_get(filename=ref)
            if d:
                text += "\n[%s]: %s\n" % (ref, d.get_url())

        # expand all non-full URLs, in case the text will be pasted onto another
        # page (or into a pdf).
        #
        # [refname]: /the/path
        text = re.sub(re.compile(r'^\[([^]]*)\]:\s*(/[^\s]*)', re.M),
                      lambda m: '[%s]: %s' % (m.group(1),
                                              urlexpander(m.group(2))),
                      text)
        # [Description String] (/the/path)
        text = re.sub(r'\[([^]]*)\]\s*\((/[^\)]*)\)',
                      lambda m: '[%s](%s)' % (m.group(1),
                                              urlexpander(m.group(2))),
                      text)
        return text

    def reference_parents(self):
        l = []
        for r in db.selectcol('select from_doc from Refs '
                              '  where to_doc=?', self.id):
            try:
                l.append(Doc(r))
            except Doc.DoesNotExist:
                pass
        return l
                
    def similar(self, max=4, minweight=0.05):
        l = []
        for weight,id in db.run('select weight,to_doc from RelatedDocs '
                                '  where from_doc=? and weight > ? '
                                '  order by weight desc'
                                '  limit ?', self.id, minweight, max):
            l.append(dict(weight=weight, doc=Doc(id)))
        return l
        
    def dissimilar(self, max=4):
        l = []
        for weight,id in db.run('select weight,to_doc from RelatedDocs '
                                '  where from_doc=? and weight > 0.001 '
                                '  order by weight asc'
                                '  limit ?', self.id, max):
            l.append(dict(weight=weight, doc=Doc(id)))
        return l

