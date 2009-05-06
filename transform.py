import xml.sax, sys, re

# p, ul/ol, li
# ol: steps->step
# ul: ul->li
# headings: task->title, prereq, context, steps
# bold: uicontrol
# draft-comment

def clean(s):
    return re.sub(r'\s+', ' ', s)

def join(between, l):
    return unicode(between).join([unicode(i) for i in l])

def die(s = "die"):
    raise Exception(s)

def indent(s, n):
    return re.sub(re.compile(r'^', re.M), ' '*n, s).strip()

class Node:
    def __init__(self, name, attrs = {}, text = ''):
	self.name = str(name)
	self.attrs = dict(attrs)
	self.text = unicode(text)
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

    def assimple(self):
	text = clean(self.text)
	for t in self:
	    if t.name in ['uicontrol', 'wintitle']:
		text += "**%s**" % clean(t.assimple())
	    elif t.name == '':
		text += clean(t.assimple())
	    elif t.name == 'p':
		text += "\n\n%s\n\n" % t.assimple()
	    else:
		die(t)
	return text

    def astext(self):
	text = []
	if self.text:
	    text.append(self.text)
	for t in self:
	    if t.name == 'stepxmp':
		pass
	    elif t.name == 'note':
		text.append("Note:\n\n- %s" % indent(t.assimple(), 2))
	    else:
		text.append(t.assimple())
	return join("\n\n", text)

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
	if top.children and top.children[-1].name == '':
	    top.children[-1].text += chars
	else:
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

def process_steps(steps, prefix):
    out = []
    for step in steps:
	t = []
	for bit in step:
	    if bit.name in ['cmd', 'stepresult']:
		t.append(bit.assimple())
	    elif bit.name == 'info':
		t.append(bit.astext())
	    elif bit.name == 'stepxmp':
		pass
	    elif bit.name == 'substeps':
		t.append(process_steps(bit, "- "))
	    else:
		die(bit)
	out.append("\n%s%s" % (prefix, indent(join("\n", t), len(prefix))))
    return join("\n", out)
    

def process_task(task, filename):
    title = filename
    tags = ['Tasks']
    body = []
    for t in task:
	if t.name == 'title':
	    title = t.astext()
	elif t.name == 'taskbody':
	    for tb in t:
		if tb.name == 'prereq':
		    if tb.nonempty():
			body.append('# Before you start')
			body.append(tb.astext())
		elif tb.name == 'context':
		    if tb.nonempty():
			#body.append('# Context')
			body.append(tb.astext())
		elif tb.name == 'steps':
		    if tb.nonempty():
			body.append('# Steps')
			body.append(process_steps(tb, "1. "))
		elif tb.name == 'postreq':
		    if tb.nonempty():
			body.append('# Next steps')
			body.append(tb.astext())
		else:
		    die(tb.name)
	else:
	    die(t.name)

    return "title: %s\ntags: %s\n\n%s" % (title, join(", ", tags),
					  join("\n\n", body))

def process(filename):
    tree = xml_to_tree(filename)
    for sub in tree.children:
	if sub.name == 'task':
	    print_node(sub)
	    print process_task(sub, filename)
	else:
	    print_node(sub)

for name in sys.argv[1:]:
    process(name)
