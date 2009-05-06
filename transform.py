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
def _die(n, list, path):
    if n == list:
	raise Exception("%s->[%s]" % (join("->", path), repr(n)))
    for i in list:
	_die(n, i, path + [list.name])
    
def die(n):
    if not treetop:
	raise Exception('treetop not set')
    _die(n, treetop, [])
    raise Exception('node not found: %s' % repr(n))

def indent(s, n):
    return re.sub(re.compile(r'^', re.M), ' '*n, s).strip()

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
	    return "\n\nNote:\n\n- %s\n\n" % indent(self.subtext(), 2)
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
	elif self.name == 'sl':
	    return process_list(self, "sli", "- ")
	elif self.name == 'ul':
	    return process_list(self, "li", "- ")
	elif self.name in ['cmd', 'stepresult', 'info', 'tutorialinfo']:
	    return self.subtext()
	else:
	    die(self)
	die(self)

    def subtext(self):
	text = self.text
	for t in self:
	    text += t.render()
	return text

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
	e.children = filter(lambda c: (c.name not in ['', 'p']
				       or c.text.strip()),
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
	if not step.name == itemname:
	    die(step)
	t = []
	for bit in step:
	    if bit.name == 'substeps':
		t.append(process_list(bit, "substep", "- "))
	    elif bit.name == 'choices':
		t.append(process_list(bit, "choice", "- "))
	    else:
		t.append(bit.render())
	out.append("\n%s%s" % (prefix, indent(join("\n", t), len(prefix))))
    return join("\n", out)
    

def process_task(task, filename):
    title = filename
    tags = ['Tasks']
    body = []
    for t in task:
	if t.name in ['title', 'shortdesc']:
	    title = t.subtext()
	elif t.name == 'taskbody':
	    for tb in t:
		if tb.name == 'prereq':
		    if tb.nonempty():
			body.append('# Before you start')
			body.append(tb.subtext())
		elif tb.name == 'context':
		    if tb.nonempty():
			#body.append('# Context')
			body.append(tb.subtext())
		elif tb.name == 'steps':
		    if tb.nonempty():
			body.append('# Steps')
			body.append(process_list(tb, "step", "1. "))
		elif tb.name == 'postreq':
		    if tb.nonempty():
			body.append('# Next steps')
			body.append(tb.subtext())
		else:
		    die(tb)
	elif t.name == 'reference':
	    pass  # FIXME
	elif t.name == 'related-links':
	    pass  # FIXME: is it okay to just leave this to the kb software?
	elif t.name == 'task':
	    pass  # FIXME: what's a task inside a task??
	else:
	    die(t)

    return "title: %s\ntags: %s\n\n%s" % (title, join(", ", tags),
					  join("\n\n", body))

def process(filename):
    tree = xml_to_tree(filename)
    global treetop
    treetop = tree
    for sub in tree.children:
	if sub.name == 'task':
	    print_node(sub)
	    pt = process_task(sub, filename)
	    print pt
	    open("%s.txt" % filename, "w").write(pt.encode('utf-8'))
	else:
	    print_node(sub)

for name in sys.argv[1:]:
    process(name)
