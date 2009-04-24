import os, time, datetime, re
from django.db import transaction
from models import Doc, Tag, Word, WordWeight, RelatedWeight

_fromtimestamp = datetime.datetime.fromtimestamp

def _flush_and_load(topdir):
    seen = {}
    id_seen = {}
    name_to_id = {}
    nextid = 1001

    # The .idmap file lets us maintain consistency between kb article numbers
    # between loads.  You might not want to check it into version control,
    # since it'll probably cause merge conflicts.  Only the public-facing
    # production server needs to maintain the numbers consistently.
    # (So that google can index things properly.)
    idfilename = "%s/.idmap" % topdir
    if os.path.exists(idfilename):
	for line in open(idfilename):
	    (id, name) = line.strip().split(" ", 1)
	    id = int(id)
	    if id in id_seen:
		raise KeyError("More than one .idmap entry for #%d" % id)
	    id_seen[id] = name
	    name_to_id[name] = id
	    nextid = max(id+1, nextid)
    idfile = open(idfilename, "a")
    
    print 'deleting all'
    Tag.objects.all().delete()
    Doc.objects.all().delete()

    print 'loading all from "%s"' % topdir
    for (dirpath, dirnames, filenames) in os.walk(topdir):
	assert(dirpath.startswith(topdir))
	tags = dirpath[len(topdir):].split("/")
	for filename in filenames:
	    if filename[-1] == '~' or filename[0] == '.':
		continue

	    if filename in seen:
		raise KeyError('Duplicate filename "%s"' % filename)
	    seen[filename] = 1
		
	    fullpath = os.path.join(dirpath, filename)

	    title = filename

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
	    print "  %s (tags=%s)" % (fullpath, repr(tags))

	    id = name_to_id.get(filename)
	    if not id:
		id = nextid
		idfile.write("%d %s\n" % (id, filename))
	    nextid = max(id+1, nextid)
		
	    d = Doc(id = id,
		    filename = filename,
		    title = title,
		    last_modified = _fromtimestamp(os.stat(fullpath)[8]),
		    text = f.read())
	    d.save()
	    for tname in tags:
		(t, created) = Tag.objects.get_or_create(name=tname)
		d.tags.add(t)

def _calc_word_frequencies():
    Word.objects.all().delete()
    WordWeight.objects.all().delete()
    
    globwords = {}
    for doc in Doc.objects.iterator():
	print ' %s' % doc.filename
	words = [w.lower() for w in re.findall(r"(\w+(?:[.']\w+)?)", doc.text)]
	total = len(words)*1.0
	d = {}
	print '   %d total words' % total
	for w in words:
	    d[w] = d.get(w, 0) + 1
	print '   %d unique words' % len(d.keys())
	new = 0
	for w in d:
	    count = d[w]
	    word = globwords.get(w)
	    if not word:
		word = Word.objects.create(name=w, total=0)
		globwords[w] = word
		new += 1
	    word.total += count
	    ww = WordWeight.objects.create(word=word, doc=doc,
					   weight=(count/total)**.5)
	print '   %d new words' % new
    print ' %d total unique words' % len(globwords)
    for word in globwords.values():
	word.save()

def _calc_related_matrix():
    print 'Calculating related documents'
    docs = list(Doc.objects.all())
    docwords = {}
    for doc in docs:
	l = docwords[doc] = {}
	for ww in doc.wordweight_set.iterator():
	    l[ww.word.name] = ww.weight

    correlations = {}
    for doc in docs:
	l = correlations[doc] = {}
	for doc2 in docs:
	    if doc2==doc: continue
	    bits = [docwords[doc2].get(word,0)*weight
		      for word,weight in docwords[doc].iteritems()]
	    l[doc2] = sum(bits)

    for doc in correlations:
	print '%s:' % doc.filename
	for doc2,weight in sorted(correlations[doc].items(),
			   lambda x,y: cmp(y[1], x[1])):
	    RelatedWeight.objects.create(parent=doc, doc=doc2, weight=weight)
	    print '  %s: %f' % (doc2.filename, weight)

def load_all(topdir):
    transaction.enter_transaction_management()
    transaction.managed()
    _flush_and_load(topdir)
    _calc_word_frequencies()
    _calc_related_matrix()
    print 'Committing'
    transaction.commit()
