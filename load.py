import sys, os, re
from django.db import transaction
from ekb.models import parse_doc, Doc, db, DOCDIR
from handy import join

def echo(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def _load_docs():
    seen = {}
    
    titlemap = {}
    for doc in Doc.search():
        if not os.path.exists(os.path.join(DOCDIR, doc.pathname)):
            print 'Deleting old document: %r %r' % (DOCDIR, doc.pathname)
            doc.delete()
        else:
            titlemap[doc.title] = doc
            
    print 'Loading all from "%s"' % DOCDIR
    for (dirpath, dirnames, filenames) in os.walk(DOCDIR):
        assert(dirpath.startswith(DOCDIR))
        for basename in filenames:
            fullpath = os.path.join(dirpath, basename)
            dirfile = fullpath[len(DOCDIR):]
            if (basename[-1] == '~' 
                or basename[0] == '.' or fullpath.find('/.') >= 0
                or basename=='Makefile'):
                   continue
            echo("  %s" % fullpath)

            if basename in seen:
                raise KeyError('Duplicate basename "%s"' % basename)
            seen[basename] = 1
                
            title = basename

            (title, tags, mtime, text) = parse_doc(dirfile)
            print " (tags=%s)" % repr(tags)

            while title in titlemap and titlemap[title].filename != basename:
                print ('WARNING: Duplicate title:\n  "%s"\n  "%s"'
                       % (basename, titlemap[title].filename))
                title += " [duplicate]"

            d = Doc.create(basename, dirfile, title)
            titlemap[title] = d
            d.use_latest()  # FIXME: lame: this parses a second time
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


def load_docs():
    _load_docs()
    print 'Committing'
    db.commit()

def index_docs():
    _calc_word_frequencies()
    _calc_related_matrix()
    print 'Committing'
    db.commit()
