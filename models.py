from settings import DEBUG
from django.db import models
import re

class Tag(models.Model):
    name = models.CharField(max_length=200, db_index=True, unique=True)

class Word(models.Model):
    name = models.CharField(max_length=40, db_index=True, unique=True)
    total = models.IntegerField()

_includes_in_progress = {}
class Doc(models.Model):
    filename = models.CharField(max_length=200, db_index=True, unique=True)
    pathname = models.CharField(max_length=400, db_index=False, unique=True)
    title = models.CharField(max_length=200, db_index=True, unique=True)
    last_modified = models.DateTimeField()
    tags = models.ManyToManyField(Tag)
    related = models.ManyToManyField('self', through='RelatedWeight',
				     symmetrical=False)
    words = models.ManyToManyField(Word, through='WordWeight')

    @staticmethod
    def try_get(**kwargs):
    	for i in Doc.objects.filter(**kwargs):
	    return i
	return None

    def get_url(self):
	#return "/kb/%d/%s" % (self.id, self.filename)
	return "/kb/%d" % self.id

    def _try_include(self, indent, filename, isfaq):
	indent = indent and int(indent) or 0
	d = Doc.try_get(filename=str(filename))
	if filename in _includes_in_progress:
	    return '[[aborted-recursive-include:%s]]' % filename
	elif not d:
	    return '[[missing-include:%s]]' % filename
	else:
	    _includes_in_progress[filename] = 1
	    t = self._process_includes(d.text(), depth=indent+1)
	    if isfaq:
		parts = re.split(re.compile(r'^#+.*$', re.M), t)
		assert(len(parts) == 3)
		t = "%s %s\n\n%s\n\n" % ('#'*(indent+1),
					 re.sub('\n', ' ', parts[1].strip()),
					 parts[2].strip())
	    del _includes_in_progress[filename]
	    return t

    def _process_includes(self, text, depth):
	# handle "include" references.  These are our own creation (not
	# standard markdown), of the form: [[include:filename]]
	# We just replace that text with the verbatim contents of the referred
	# document.
	t = re.sub(r'\[\[(faq)?include(\+(\d+))?:([^]]*)\]\]',
		   lambda m: self._try_include(m.group(3), m.group(4),
					       m.group(1) == 'faq'),
		   text)

	# normalize the headers: the toplevel header should be h1, no matter
	# what it is in the document itself.
	allheaders = re.findall(re.compile('^(#+)', re.M), t)
	minheader = min([99] + [len(h) for h in allheaders])
	return re.sub(re.compile(r'^' + '#'*minheader, re.M), '#'*depth, t)

    def text(self):
	f = open('docs/%s' % self.pathname)
	while f.readline().strip() != '':
	    pass
	return f.read()

    def expanded_text(self, headerdepth=1):
	text = self._process_includes(self.text(), depth=headerdepth)

	# find all markdown 'refs' that refer to kb pages.
	# Markdown refs are of the form: [Description String] [refname]
	# And we need to add a line like:
	#   [refname]: /the/path
	# to the bottom in order to make the ref resolvable.
	refs = re.findall(r'\[[^]]*\]\s*\[([^]]*)\]', text)
	for ref in refs:
	    d = Doc.try_get(filename=ref)
	    if d:
		text += "\n[%s]: %s\n" % (ref, d.get_url())
	return text
		
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
