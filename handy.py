import datetime, os

def join(between, list):
    if list != None:
	return unicode(between).join([unicode(i) for i in list])
    else:
	return None

def atoi(s):
    try:
	return int(s)
    except ValueError:
	return 0
    except TypeError:
	return 0


def nicedate(d1):
    d2 = datetime.datetime.now()
    diff = d2 - d1
    days = diff.days
    secs = diff.seconds
    if secs < 0 or days < 0:
	return 'in the future'
    elif days >= 14:
	return d1.strftime('%Y-%m-%d')
    elif days >= 1:
	return '%s day%s ago' % (days, pluralize(days))
    elif secs >= 60*60:
	return 'today'
    elif secs >= 60:
	return 'minutes ago'
    else:
	return 'seconds ago'


def pluralize(n, suffix = 's'):
    if n == 1:
	return ''
    else:
	return suffix


def mkdirp(name):
    """ Create the directory 'name', including any parent folders if necessary.
    """
    try:
	os.makedirs(name)
    except OSError:
	pass


def unlink(name):
    try:
    	os.unlink(name)
    except OSError, e:
	if e.errno != 2:
	    raise

