import xml.sax, sys, re

# p, ul/ol, li
# ol: steps->step
# ul: ul->li
# headings: task->title, prereq, context, steps
# bold: uicontrol
# draft-comment

def clean(s):
    return re.sub(r'[\n\r \t]+', u' ', s)

def join(between, l):
    return unicode(between).join([unicode(i) for i in l])

treetop = None
def _die_find(n, list, path):
    if n == list:
	return path
    for i in list:
	p = _die_find(n, i, path + [list.name])
	if p:
	    return p
    
def die(n):
    if not treetop:
	raise Exception('treetop not set')
    path = _die_find(n, treetop, [])
    if path:
	raise Exception("%s->[%s]" % (join("->", path), repr(n)))
    else:
	raise Exception('node not found: %s' % repr(n))

def indent(s, prefix):
    s = s.lstrip()
    return re.sub("\n", "\n" + prefix, s).strip()

class Node:
    def __init__(self, name, attrs = {}, text = ''):
	self.name = str(name)
	self.attrs = dict(attrs)
	self.text = clean(unicode(text))
	self.children = []

    def __repr__(self):
	if self.text:
	    return repr((self.name, self.text))
	else:
	    return repr(self.name)

    def __iter__(self):
	return iter(self.children)

    def add(self, child):
	self.children.append(child)

    def render(self):
	if self.name == 'stepxmp':
	    return ''
	elif self.name == 'note':
	    st = self.subtext()
	    if st:
		return "\n\n> **Note:** %s\n\n" % indent(st, '> ')
	    else:
		return ''
	elif self.name in ['uicontrol', 'wintitle', 'userinput',
			   'filepath', 'fn', 'b']:
	    return " **%s** " % clean(self.subtext().strip())
	elif self.name in ['i']:
	    return " *%s* " % clean(self.subtext().strip())
	elif self.name == '':
	    return self.subtext()
	elif self.name == 'draft-comment':
	    return '<!-- %s -->' % self.subtext().strip()
	elif self.name == 'p':
	    return "\n\n%s\n\n" % self.subtext()
	elif self.name in ['fig', 'image']:
	    return ''   # FIXME
	elif self.name == 'substeps':
	    return process_list(self, "substep", "- ")
	elif self.name == 'choices':
	    return process_list(self, "choice", "- ")
	elif self.name == 'sl':
	    return process_list(self, "sli", "- ")
	elif self.name == 'dl':
	    return process_list(self, "dlentry", "- ")
	elif self.name == 'ul':
	    return process_list(self, "li", "- ")
	elif self.name in ['cmd', 'stepresult', 'info', 'tutorialinfo',
			   'li', 'sli', 'step', 'substep', 'choice',
			   'dlentry']:
	    return self.subtext()
	elif self.name == 'section':
	    return '\n\n# Section!\n\n%s' % self.subtext()
	elif self.name in ['title', 'dt', 'dd']:
	    # FIXME
	    return '%s(%s)' % (self.name, self.subtext())
	else:
	    die(self)
	die(self)

    def subtext(self):
	text = clean(self.text)
	for t in self:
	    text += t.render()
	return text + ' '

    def nonempty(self):
	return self.text or self.children

class TreeHandler(xml.sax.ContentHandler):
    def __init__(self):
	xml.sax.ContentHandler.__init__(self)
	self.root = Node('root')
	self.stack = [self.root]

    def startElement(self, name, attrs):
	e = Node(name, attrs = attrs)
	self.stack[-1].add(e)
	self.stack.append(e)

    def endElement(self, name):
	e = self.stack.pop()

	# if *all* children are plaintext, join them together into this node's
	# 'text' member
	if not filter(lambda c: c.name, e.children):
	    for c in e.children:
		e.text += c.text
	    e.children = []

	# empty text nodes are boring
	e.children = filter(lambda c: (c.name not in ['', 'p', 'note']
				       or c.text.strip()
				       or c.subtext().strip()),
			    e.children)

    def characters(self, chars):
	top = self.stack[-1]
	e = Node('', text = chars)
	top.add(e)

def xml_to_tree(filename):
    p = xml.sax.make_parser()
    p.setFeature('http://xml.org/sax/features/validation', False)
    p.setFeature("http://xml.org/sax/features/external-general-entities", False)
    h = TreeHandler()
    p.setContentHandler(h)
    p.parse(open(filename))
    return h.root

def print_tree(children, indent):
    for n in children:
	print_node(n, indent)

def print_node(n, indent = 0):
    print '%s%s' % (' '*indent, repr(n))
    print_tree(n.children, indent+4)

def process_list(steps, itemname, prefix):
    out = []
    for step in steps:
	if step.name == 'dlhead':
	    continue  # FIXME
	if not step.name == itemname:
	    die(step)
	t = step.render().strip()
	if t:
	    out.append("\n%s%s" % (prefix, indent(t, '    ')))
    return join("\n", out)
    

def process_task(task, filename):
    title = filename
    tags = ['Tasks']
    body = []
    for t in task:
	if t.name in ['title', 'shortdesc']:
	    title = t.subtext()
	elif t.name in ['taskbody']:
	    for tb in t:
		if tb.name == 'prereq':
		    if tb.nonempty():
			st = tb.subtext()
			if st:
			    body.append('# Before you start')
			    body.append(st)
		elif tb.name == 'context':
		    if tb.nonempty():
			st = tb.subtext()
			if st:
			    body.append('# Context')
			    body.append(st)
		elif tb.name == 'steps':
		    if tb.nonempty():
			pl = process_list(tb, "step", "1. ")
			if pl:
			    body.append('# Steps')
			    body.append(pl)
		elif tb.name == 'postreq':
		    if tb.nonempty():
			st = tb.subtext()
			if st:
			    body.append('# Next steps')
			    body.append(st)
		else:
		    die(tb)
	elif t.name == 'body':
	    body.append(t.subtext())
	elif t.name == 'reference':
	    pass  # FIXME
	elif t.name == 'related-links':
	    pass  # FIXME: is it okay to just leave this to the kb software?
	elif t.name == 'task':
	    pass  # FIXME: what's a task inside a task??
	else:
	    die(t)

    if body:
	return "title: %s\ntags: %s\n\n%s" % (title, join(", ", tags),
					      join("\n\n", body))

def process(filename):
    tree = xml_to_tree(filename)
    global treetop
    treetop = tree
    print_node(tree)
    for sub in tree:
	pt = None
	if sub.name in ['task', 'topic']:
	    pt = process_task(sub, filename)
	if pt:
	    print pt.encode('utf-8')
	    open("%s.txt" % filename, "w").write(pt.encode('utf-8'))
	else:
	    print 'Skipping %s' % filename

for name in sys.argv[1:]:
    process(name)

print 'done'
