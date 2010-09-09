import sys, os, re
from django.db import transaction
from ekb.models import parse_doc, Doc, db
from handy import join

def echo(s):
    sys.stdout.write(s)
    sys.stdout.flush()


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
    
    titlemap = {}
    for doc in Doc.search():
        if not os.path.exists(topdir + doc.pathname):
            print 'Deleting old document: %s' % doc.filename
            doc.delete()
        else:
            titlemap[doc.title] = doc
            
    print 'Loading all from "%s"' % topdir
    for (dirpath, dirnames, filenames) in os.walk(topdir):
        assert(dirpath.startswith(topdir))
        for basename in filenames:
            fullpath = os.path.join(dirpath, basename)
            dirfile = fullpath[len(topdir):]
            if (basename[-1] == '~' 
                or basename[0] == '.' or fullpath.find('/.') >= 0
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

            while title in titlemap and titlemap[title].filename != basename:
                print ('WARNING: Duplicate title:\n  "%s"\n  "%s"'
                       % (basename, titlemap[title].filename))
                title += " [duplicate]"

            db.run('insert or replace into Docs '
                   '  (id, filename, pathname, title, mtime) '
                   '  values (?,?,?,?,?)',
                   id, basename, dirfile, title, mtime)
            titlemap[title] = d = Doc(id)
            d.use_latest()
            d.title = title
            d.save()


def _calc_word_frequencies():
    print 'Deleting all wordweights'
    db.run('delete from WordWeights')
    db.run('delete from Words')
    
    totals = {}
    for doc in Doc.search():
        print ' %s' % doc.filename
        textbits = [doc.title, doc.title,  # title gets bonus points
                    doc.filename, doc.expanded_text(lambda x: x, headerdepth=1,
                                                    expandbooks=1)]
        textbits += doc.tags
        fulltext = join(' ', textbits)
        words = [w.lower() for w in re.findall(r"(\w+(?:[.'#%@]\w+)?)",
                                               fulltext)]
        total = len(words)*1.0
        wordcounts = {}
        echo('   %d total words' % total)
        for w in words:
            wordcounts[w] = wordcounts.get(w, 0) + 1
        echo(', %d unique' % len(wordcounts.keys()))
        new = 0
        for w,count in wordcounts.iteritems():
            if not w in totals:
                totals[w] = 0
                new += 1
            totals[w] += count
            db.run('insert into WordWeights (docid, word, weight) '
                   '  values (?,?,?)', doc.id, w, (count/total)**.5)
        echo(', %d new\n' % new)
    print ' %d total unique words' % len(totals)
    print 'Saving words'
    for word,count in totals.iteritems():
        db.run('insert into Words (word, total) values (?,?)', word, count)


def _calc_related_matrix():
    print 'Deleting all relatedweights'
    db.run('delete from RelatedDocs')
    
    print 'Reading word weights'
    docs = list(Doc.search())
    docwords = {}
    for doc in docs:
        echo('.')
        l = docwords[doc] = {}
        for word,weight in db.run('select word,weight from WordWeights '
                                  '  where docid=?', doc.id):
            l[word] = weight
    print
    
    print 'Calculating related documents'
    correlations = {}
    for doc in docs:
        echo('.')
        l = correlations[doc] = {}
        for doc2 in docs:
            if doc2==doc: continue
            bits = (docwords[doc2].get(word,0)*weight
                      for word,weight in docwords[doc].iteritems())
            l[doc2] = sum(bits)
    print
    
    print 'Saving correlations'
    for doc in correlations:
        #print '%s:' % doc.filename
        for doc2,weight in correlations[doc].items():
            db.run('insert or replace into RelatedDocs '
                   '  (from_doc, to_doc, weight) '
                   '  values (?,?,?)', doc.id, doc2.id, weight)
            #print '  %s: %f' % (doc2.filename, weight)


def load_docs(topdir):
    _load_docs(topdir)
    print 'Committing'
    db.commit()

def index_docs(topdir):
    _calc_word_frequencies()
    _calc_related_matrix()
    print 'Committing'
    db.commit()
