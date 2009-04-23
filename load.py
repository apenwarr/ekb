import os, time, datetime
from models import Doc, Tag

_fromtimestamp = datetime.datetime.fromtimestamp

def load_all(path):
    print 'deleting all'
    Tag.objects.all().delete()
    Doc.objects.all().delete()

    nextid = 1000

    print 'loading all from "%s"' % path
    for (dirpath, dirnames, filenames) in os.walk(path):
	assert(dirpath.startswith(path))
	tags = dirpath[len(path):].split("/")
	for filename in filenames:
	    if filename[-1] == '~' or filename[0] == '.':
		continue
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

	    print "  %s (tags=%s)" % (fullpath, repr(tags))
	    
	    nextid += 1
	    d = Doc(id = nextid,
		    filename = filename,
		    title = title,
		    last_modified = _fromtimestamp(os.stat(fullpath)[8]),
		    text = f.read())
	    d.save()
	    for tname in filter(None, tags):
		(t, created) = Tag.objects.get_or_create(name=tname)
		d.tags.add(t)
