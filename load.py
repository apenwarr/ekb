import sys, os, re
from django.db import transaction
from ekb.models import parse_doc, Doc, Tag, Word, WordWeight, RelatedWeight
from handy import join

def echo(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def flush():
    print 'deleting all'
    Tag.objects.all().delete()
    Doc.objects.all().delete()

def _load_docs(topdir):
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
    
    print 'loading all from "%s"' % topdir
    titlemap = {}
    for (dirpath, dirnames, filenames) in os.walk(topdir):
	assert(dirpath.startswith(topdir))
	for basename in filenames:
	    fullpath = os.path.join(dirpath, basename)
	    dirfile = fullpath[len(topdir):]
	    if (basename[-1] == '~' or basename[0] == '.'
	        or basename=='Makefile'):
		   continue
	    echo("  %s" % fullpath)

	    if basename in seen:
		raise KeyError('Duplicate basename "%s"' % basename)
	    seen[basename] = 1
		
	    title = basename

	    (title, tags, mtime, text) = parse_doc(topdir, dirfile)

	    print " (tags=%s)" % repr(tags)

	    id = name_to_id.get(basename)
	    if not id:
		id = nextid
		idfile.write("%d %s\n" % (id, basename))
	    nextid = max(id+1, nextid)

	    while title in titlemap:
		print ('WARNING: Duplicate title:\n  "%s"\n  "%s"'
		       % (basename, titlemap[title].filename))
		title += " [duplicate]"
		
	    d = Doc(id = id,
		    filename = basename,
		    pathname = dirfile,
		    title = title,
		    last_modified = mtime)
	    titlemap[title] = d
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
	textbits = [doc.title, doc.title,  # title gets bonus points
		    doc.filename, doc.expanded_text()]
	textbits += [t.name for t in doc.tags.all()]
	fulltext = join(' ', textbits)
	words = [w.lower() for w in re.findall(r"(\w+(?:[.'#%@]\w+)?)", fulltext)]
	total = len(words)*1.0
	d = {}
	echo('   %d total words' % total)
	for w in words:
	    d[w] = d.get(w, 0) + 1
	echo(', %d unique' % len(d.keys()))
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
	echo(', %d new\n' % new)
    print ' %d total unique words' % len(globwords)
    print 'Saving words'
    for word in globwords.values():
	word.save()

def _calc_related_matrix():
    print 'Reading word weights'
    docs = list(Doc.objects.all())
    docwords = {}
    for doc in docs:
        echo('.')
	l = docwords[doc] = {}
	for ww in doc.wordweight_set.iterator():
	    l[ww.word.name] = ww.weight
    print

    print 'Calculating related documents'
    correlations = {}
    for doc in docs:
        echo('.')
	l = correlations[doc] = {}
	for doc2 in docs:
	    if doc2==doc: continue
	    bits = [docwords[doc2].get(word,0)*weight
		      for word,weight in docwords[doc].iteritems()]
	    l[doc2] = sum(bits)
    print

    print 'Saving correlations'
    for doc in correlations:
	#print '%s:' % doc.filename
	for doc2,weight in sorted(correlations[doc].items(),
			   lambda x,y: cmp(y[1], x[1])):
	    RelatedWeight.objects.create(parent=doc, doc=doc2, weight=weight)
	    #print '  %s: %f' % (doc2.filename, weight)

def load_all(topdir):
    transaction.enter_transaction_management()
    transaction.managed()
    flush()
    _load_docs(topdir)
    _calc_word_frequencies()
    _calc_related_matrix()
    print 'Committing'
    transaction.commit()
