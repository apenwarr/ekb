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


def nicedate(diff):
    ''' Return a string representing the datediff "diff".
        "diff" should be produced by subtracting two datetime.datetime
	objects.
    '''
    days = diff.days
    secs = diff.seconds
    if secs < 0 or days < 0:
	return 'in the future'
    elif days >= 30:
	return '%s month%s ago' % (days/30, pluralize(days))
    elif days >= 1:
	return '%s day%s ago' % (days, pluralize(days))
    elif secs >= 60*60:
	return '%s hour%s ago' % (secs/60/60, pluralize(secs/60/60))
    elif secs >= 60:
	return '%s minute%s ago' % (secs/60, pluralize(secs/60))
    else:
	return '%s second%s ago' % (secs, pluralize(secs))


def pluralize(n, suffix = 's'):
    if n == 1:
	return ''
    else:
	return suffix

