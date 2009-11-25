from settings import DEBUG
from django.db import models
from django.core.urlresolvers import NoReverseMatch
from django.utils import html
import re, os, datetime

class Tag(models.Model):
    name = models.CharField(max_length=200, db_index=True, unique=True)

class Word(models.Model):
    name = models.CharField(max_length=40, db_index=True, unique=True)
    total = models.IntegerField()

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
    mtime = datetime.datetime.fromtimestamp(os.stat(fullpath)[8])
    return (title, tags, mtime, f.read().decode('utf-8'))

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
    sortwords = [w.name for w in 
                 Word.objects.filter(name__in = want_words).order_by('total')]

    # get rid of some markdown cruft
    text = re.sub(re.compile('^#+(.*)(\S)\s*$', re.M),
                  lambda m: _fixheader(m.group(1), m.group(2)),
                  text)
    text = re.sub(r'\!\[(.*?)\]\s*\(.*?\)', r'', text)
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

    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    if highlighter:
        return highlighter(text, html.escape) + hi
    else:
        return text + hi

_includes_in_progress = {}
class Doc(models.Model):
    filename = models.CharField(max_length=200, db_index=True, unique=True)
    pathname = models.CharField(max_length=400, db_index=False, unique=True)
    title = models.CharField(max_length=200, db_index=True, unique=True)
    last_modified = models.DateTimeField()
    tags = models.ManyToManyField(Tag)
    related = models.ManyToManyField('self', through='RelatedWeight',
                                     symmetrical=False)
    reference_to = models.ManyToManyField('self',
                                          related_name = 'reference_from')
    words = models.ManyToManyField(Word, through='WordWeight')

    @staticmethod
    def try_get(**kwargs):
        for i in Doc.objects.filter(**kwargs):
            return i
        return None

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

    _title = None
    _tags = None
    _text = None
    def read_latest(self):
        (self._title, self._tags, self.last_modified, self._text) \
                = parse_doc('docs', self.pathname)

    def use_latest(self):
        if not self._text:
            self.read_latest()
        self.title = self._title
        for tname in self._tags:
            (t, created) = Tag.objects.get_or_create(name=tname)
            self.tags.add(t)
        for t in list(self.tags.all()):
            if not t.name in self._tags:
                self.tags.remove(t)
        refs = parse_refs(self._text)
        for rname in refs:
            (r, created) = Reference.objects.get_or_create(parent=self.filename,
                                                           child=rname)
            r.save()
        for r in list(Reference.objects.filter(parent=self.filename)):
            if not r.child in refs:
                r.delete()

    def _try_include(self, indent, filename, isfaq, skipto, expandbooks):
        indent = indent and int(indent) or 0
        d = Doc.try_get(filename=str(filename))
        if filename in _includes_in_progress:
            return '[[aborted-recursive-include:%s]]' % filename
        elif not d:
            return '[[missing-include:%s]]' % filename
        else:
            _includes_in_progress[filename] = 1
            t = self._process_includes(d.text(), depth=indent+1,
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
            return ("%s %s\n%s [(Read more)][%s]\n\n"
                    % (pounds, text, summary, ref))

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

    def text(self):
        if not self._text:
            self.read_latest()
        return self._text

    def expanded_text(self, urlexpander, headerdepth, expandbooks):
        text = self._process_includes(self.text(), depth=headerdepth,
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
        for r in Reference.objects.filter(child=self.filename):
            try:
                l.append(Doc.objects.get(filename=r.parent))
            except Doc.DoesNotExist:
                pass
        return l
                
    def similar(self, max=4, minweight=0.05):
        return (self.related_to
                    .order_by('-weight')
                    .filter(weight__gt=minweight)
                    [:max])
        
    def dissimilar(self, max=4):
        return (self.related_to
                    .order_by('weight')
                    .filter(weight__gt=0.001)
                    [:max])

class WordWeight(models.Model):
    word = models.ForeignKey(Word)
    doc = models.ForeignKey(Doc)
    weight = models.FloatField()

class RelatedWeight(models.Model):
    parent = models.ForeignKey(Doc, related_name = 'related_to')
    doc = models.ForeignKey(Doc, related_name = 'related_from')
    weight = models.FloatField()

class Reference(models.Model):
    parent = models.CharField(max_length=200, db_index=True)
    child = models.CharField(max_length=200, db_index=True)
