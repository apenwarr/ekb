import os, time, datetime
from models import Doc, Tag

_fromtimestamp = datetime.datetime.fromtimestamp

def load_all(path):
    print 'deleting all'
    Doc.objects.all().delete()

    print 'loading all from "%s"' % path
    for (dirpath, dirnames, filenames) in os.walk(path):
	assert(dirpath.startswith(path))
	tags = filter(None, dirpath[len(path):].split("/"))
	for f in filenames:
	    fullpath = os.path.join(dirpath, f)
	    print "  %s (tags=%s)" % (fullpath, repr(tags))

	    d = Doc(title = f,
		    last_modified = _fromtimestamp(os.stat(fullpath)[8]),
		    text = open(fullpath).read())
	    d.save()
	    for tname in tags:
		t = Tag.objects.get(name=tname)
		if not t:
		    t = Tag(name=tname)
		    t.save()
		d.tags.add(t)
