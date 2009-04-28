from django.db import models
import re

def _try_get(queryset, **kwargs):
    for i in queryset.filter(**kwargs):
	return i
    return None

class Tag(models.Model):
    name = models.CharField(max_length=200, db_index=True, unique=True)

class Word(models.Model):
    name = models.CharField(max_length=40, db_index=True, unique=True)
    total = models.IntegerField()

_includes_in_progress = {}
class Doc(models.Model):
    filename = models.CharField(max_length=200, db_index=True, unique=True)
    title = models.CharField(max_length=200, db_index=True, unique=True)
    last_modified = models.DateTimeField()
    tags = models.ManyToManyField(Tag)
    related = models.ManyToManyField('self', through='RelatedWeight',
				     symmetrical=False)
    words = models.ManyToManyField(Word, through='WordWeight')
    text = models.TextField()

    def get_url(self):
	return "/kb/%d/%s" % (self.id, self.filename)

    def _try_include(self, match):
	indent = match.group(2)
	indent = indent and int(indent) or 0
	refname = match.group(3)
	d = _try_get(Doc.objects, filename=str(refname))
	if refname in _includes_in_progress:
	    return '[[aborted-recursive-include:%s]]' % refname
	elif d:
	    _includes_in_progress[refname] = 1
	    t = self._process_includes(d.text, depth=indent+1)
	    del _includes_in_progress[refname]
	    return t
	else:
	    return '[[missing-include:%s]]' % refname

    def _process_includes(self, text, depth):
	# handle "include" references.  These are our own creation, of the
	# form: [[include:refname]]
	# We just replace that text with the verbatim contents of the referred
	# document.
	t = re.sub(r'\[\[include(\+(\d+))?:([^]]*)\]\]', self._try_include, text)

	# normalize the headers: the toplevel header should be h1, no matter
	# what it is in the document itself.
	allheaders = re.findall(re.compile('^(#+)', re.M), t)
	minheader = min([99] + [len(h) for h in allheaders])
	return re.sub(re.compile(r'^' + '#'*minheader, re.M), '#'*depth, t)

    def expanded_text(self, depth=1):
	return self._process_includes(self.text, depth=depth)

    def similar(self, max=4):
	return (self.related_to
		    .order_by('-weight')
		    .filter(weight__gt=0.05)
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
