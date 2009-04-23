import os, time, datetime
from models import Doc, Tag

_fromtimestamp = datetime.datetime.fromtimestamp

def load_all(topdir):
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
	    for tname in filter(None, tags):
		(t, created) = Tag.objects.get_or_create(name=tname)
		d.tags.add(t)
