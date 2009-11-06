import xml.sax, sys, re, os
from handy import *

def fixname(filename):
    if filename.endswith(".xml"):
        filename = filename[:-4]
    elif filename.endswith(".ditamap"):
        filename = filename[:-8]
    return filename


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


class XmlNode:
    def __init__(self, name, attrs={}):
        self.name = str(name)
        self.attrs = dict(attrs)
        self.children = []

    def __repr__(self):
        if self.attrs:
            return "<%s %s>" % (self.name, repr(self.attrs))
        else:
            return "<%s>" % self.name

    def __iter__(self):
        return iter(self.children)

    def add(self, child):
        self.children.append(child)

    def subtext(self):
        return join('', [i.subtext() for i in self])


class TextXmlNode(XmlNode):
    def __init__(self, text):
        XmlNode.__init__(self, '')
        self.text = text

    def __repr__(self):
        return repr(self.text)

    def subtext(self):
        return self.text
    

class TreeHandler(xml.sax.ContentHandler):
    def __init__(self):
        xml.sax.ContentHandler.__init__(self)
        self.root = XmlNode('root')
        self.stack = [self.root]

    def startElement(self, name, attrs):
        e = XmlNode(name, attrs = attrs)
        self.stack[-1].add(e)
        self.stack.append(e)
        #print 'se(%s)' % repr(name)

    def endElement(self, name):
        e = self.stack.pop()
        #print 'ee(%s)' % repr(name)

    def characters(self, chars):
        #print 'tx(%s)' % repr(chars)
        top = self.stack[-1]
        e = TextXmlNode(text = chars)
        top.add(e)
        

def xml_to_tree(filename):
    p = xml.sax.make_parser()
    p.setFeature('http://xml.org/sax/features/validation', False)
    p.setFeature("http://xml.org/sax/features/external-general-entities", False)
    h = TreeHandler()
    p.setContentHandler(h)
    p.parse(open(filename))
    return h.root


def print_xmltree(children, indent):
    for n in children:
        print_xmlnode(n, indent)


def print_xmlnode(n, indent = 0):
    print '%s%s' % (' '*indent, repr(n))
    print_xmltree(n.children, indent+4)


class Element:
    def __init__(self):
        self._tags = {}

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.render(1)))

    def dump(self, indent):
        print indent + self.__class__.__name__

    def render(self, raw):
        #print 'rendering(%s)' % self.__class__.__name__
        return ""

    def tags(self):
        return self._tags

    def add_tag(self, tag):
        self._tags[tag] = 1
        return self


class Literal(Element):
    def __init__(self, text):
        Element.__init__(self)
        assert(isinstance(text, basestring))
        self.text = text

    def dump(self, indent):
        Element.dump(self, indent)
        print "%s    %s" % (indent, repr(self.text))

    def render(self, raw):
        #print 'rendering(%s)' % self.__class__.__name__
        if raw:
            return self.text
        else:
            return re.sub(r'[\n\r \t]+', u' ', self.text)


class Span(Element):
    def __init__(self, items):
        Element.__init__(self)
        assert(isinstance(items, list))
        for i in items:
            assert(isinstance(i, Element))
        self.items = items

    def dump(self, indent):
        Element.dump(self, indent)
        for i in self.items:
            i.dump(indent + '    ')

    def render_item(self, item, raw):
        return item.render(raw)

    def render(self, raw):
        #print 'rendering(%s)' % self.__class__.__name__
        out = []
        for i in self.items:
            out.append(self.render_item(i, raw))
        return join("", out)

    def tags(self):
        t = Element.tags(self)
        for i in self.items:
            t.update(i.tags())
        return t


class Block(Span):
    def __init__(self, lineprefix, items):
        Span.__init__(self, items)
        assert(isinstance(lineprefix, basestring))
        self.lineprefix = lineprefix

    def render(self, raw):
        #print 'rendering(%s)' % self.__class__.__name__
        t = Span.render(self, raw)
        if not raw:
            t = t.strip()
        t = re.sub("\n", "\n%s" % self.lineprefix, t)
        return "\n\n%s\n" % t


class PrefixBlock(Block):
    def __init__(self, firstprefix, lineprefix, items):
        Block.__init__(self, lineprefix, items)
        assert(isinstance(firstprefix, basestring))
        self.firstprefix = firstprefix

    def render(self, raw):
        t = Block.render(self, raw).strip()
        if t.strip():
            return "\n\n%s%s\n" % (self.firstprefix, t)
        else:
            return ''


class List(Block):
    def __init__(self, itemprefix, lineprefix, items):
        Block.__init__(self, lineprefix, items)
        assert(isinstance(itemprefix, basestring))
        self.itemprefix = itemprefix

    def render_item(self, item, raw):
        if isinstance(item, Block) and item.render(0).strip():
            ri = Block.render_item(self, item, raw).lstrip()
            ri = re.sub("\n", "\n%s" % self.lineprefix, ri)
            return (self.itemprefix + ri)
        else:
            #print repr(item.render(0).strip())
            #assert(not item.render(0).strip())
            if item.render(0).strip():
                print 'yyy: %s' % repr(item.__class__.__name__)
                print 'xxx: %s' % repr(item.render(0).strip())
                assert(0)
            return ''

    def render(self, raw):
        # Yes, this really should be Span.render(), not Block.render().
        # Block does its lineprefix in render(), but we need to do it in
        # render_item(), since the first bit of every item is special.
        t = Span.render(self, raw)
        if not raw:
            t = re.sub(r'^\s+|\s+$', '', t)
        return "\n%s\n" % t


class Section(Block):
    def __init__(self, title, items, force = 0):
        Block.__init__(self, '', items)
        assert(title is None or isinstance(title, basestring))
        self.title = title
        self.force = force

    def render(self, raw):
        #print 'rendering(%s)' % self.__class__.__name__
        t = Block.render(self, raw)
        if self.title and (self.force or t.strip()):
            t = re.sub(re.compile("^#", re.M), "##", t)
            return "\n# %s\n%s" % (self.title, t)
        else:
            return t

    def steal_title(self):
        if not self.title:
            for i in self.items:
                if isinstance(i, Section):
                    self.title = i.steal_title()
        t = self.title
        self.title = None
        return t


def _subs(n):
    return list(filter(None, [parse_element(sub) for sub in n]))

def _title(top):
    for n in top:
        if n.name == 'title':
            return re.sub(r'\s+', ' ', n.subtext()).strip()

# WARNING: may return None
def parse_element(n):
    #print 'pe(%s)' % n
    assert(isinstance(n, XmlNode))
    if isinstance(n, TextXmlNode):
        return Literal(n.text)
    elif n.name in ['root',
                    'task', 'taskbody',
                    'concept', 'conbody', 'section',
                    'topic', 'body',
                    'dita', 'fm-ditafile',
                    'reference', 'refbody', 'refsyn',
                    'fig']:
        s = Section(_title(n), _subs(n))
        if n.name == 'task':
            s.add_tag('Tasks')
        elif n.name == 'concept':
            s.add_tag('Concepts')
        return s
    elif n.name in ['map']:
        return Section(n.attrs['title'], _subs(n)).add_tag('Books')
    elif n.name in ['topichead']:
        return Section(n.attrs['navtitle'], _subs(n))
    elif n.name in ['topicref']:
        href = fixname(n.attrs['href'])
        title = n.attrs['navtitle']
        return Section("[%s][%s]" % (title, href), _subs(n), force=1)
    elif n.name in ['prereq']:
        return PrefixBlock('**Prerequisites:** ', '', _subs(n))
    elif n.name in ['postreq']:
        return Section('Afterwards', _subs(n))
    elif n.name in ['context']:
        return Section('', _subs(n))
    elif n.name in ['choices', 'substeps', 'sl', 'ul', 'steps-unordered']:
        return List('\n- ', '    ', _subs(n))
    elif n.name in ['dl']:
        return List('\n- ', '    ', _subs(n))
    elif n.name in ['dlhead', 'dthd', 'ddhd', 'dlentry']:
        # FIXME: handle terms and definitions separately
        return Block('', _subs(n))
    elif n.name in ['dt']:
        return Span([Literal('**')] + _subs(n) + [Literal(':** ')])
    elif n.name in ['dd']:
        return Span(_subs(n))
    elif n.name in ['steps', 'ol']:
        return List('\n1. ', '    ', _subs(n))
    elif n.name in ['step', 'p', 'cmd', 'stepresult', 'choice', 'stepxmp',
                    'substep', 'shortdesc', 'sli', 'tutorialinfo', 'li',
                    'tbody', 'tgroup']:
        return Block('', _subs(n))
    elif n.name in ['table', 'simpletable']:
        return Block('', 
                     [Literal('<table class="pretty">')] 
                     + _subs(n)
                     + [Literal('</table>')])
    elif n.name in ['thead', 'sthead']:
        return Block('',
                     [Literal('<tr class="header">')] 
                     + _subs(n) + [Literal('</tr>')])
    elif n.name in ['row', 'strow']:
        return Block('',
                     [Literal('<tr>')] + _subs(n) + [Literal('</tr>')])
    elif n.name in ['entry', 'stentry']:
        return Block('',
                     [Literal('<td>')] + _subs(n) + [Literal('</td>')])
    elif n.name in ['note']:
        return PrefixBlock('> **Note:** ', '> ', _subs(n))
    elif n.name in ['draft-comment']:
        return PrefixBlock('> **DRAFT FIXME:** ', '> ', _subs(n))
    elif n.name in ['lines']:
        return Block('    ', [Literal('    ')] + _subs(n))
    elif n.name in ['info']:
        #return Block('', [Literal('<i>')] + _subs(n) + [Literal('</i>')])
        return Block('', _subs(n))
    elif n.name in ['uicontrol', 'wintitle', 'b', 'userinput']:
        return Span([Literal('**')] + _subs(n) + [Literal('**')])
    elif n.name in ['i', 'fn', 'filepath']:
        return Span([Literal('*')] + _subs(n) + [Literal('*')])
    elif n.name in ['title']:
        pass  # already handled this in _title() earlier
    elif n.name in ['image']:
        href = n.attrs['href'].replace("\\", "/")
        base = os.path.basename(href)
        return Block('', [Literal('![%s](/static/kbfiles/%s)'
                                  % (base, base))])
    elif n.name in ['related-links', 'indexterm',
                    'colspec']:
        pass
    else:
        die(n)


def process(outdir, filename):
    print "\n===================="
    print 'file: %s' % filename
    
    tree = xml_to_tree(filename)
    global treetop
    treetop = tree
    print_xmlnode(tree)
    print "--------------------\n"

    pt = parse_element(tree)
    pt.dump('')
    print "--------------------\n"

    title = pt.steal_title()
    tags = pt.tags()
    text = pt.render(0).strip()
    if text:
        text = "\n%s\n" % text
        prefix = ''
        if title:
            prefix += "title: %s\n" % title
            tagwords = {'agent': 'Agents',
                        'client': 'Clients',
                        'rsp': 'RSPs',
                        'gic': 'GICs',
                        'statement': 'Statements',
                        'estate': 'Estates',
                        'sunrise': 'Sunrise Savings',
                        'application': 'Applications',
                        'nominee': 'Nominees',
                        'import': 'Importing',
                        'commission': 'Commission',
                        'interest': 'Interest Rates',
                        'rate': 'Interest Rates',
                        'decd': 'Estates',
                        'death': 'Estates',
                        'decease': 'Estates',
                        'c-': 'Concepts',
                        'autoroll': 'Rollover',
                        'auto-roll': 'Rollover',
                        'rollover': 'Rollover',
                        'cheque': 'Cheques',
                        'certificate': 'Certificates',
                        'deposit': 'Deposits/Withdrawals',
                        'withdraw': 'Deposits/Withdrawals',
                        'transfer': 'Deposits/Withdrawals',
                        'match': 'Matching Screen',
                        'payout': 'Payout Instructions',
                        'report': 'Reports',
                        }
            for k,v in tagwords.items():
                if title.lower().find(k) >= 0:
                    tags[v] = 1
        if not tags:
            tags['Other'] = 1
        if tags:
            prefix += "tags: %s\n" % (join(", ", tags.keys()))
        fulltext = "%s\n%s\n" % (prefix, text)
        enc = fulltext.encode('utf-8')
        print enc

        basename = fixname(filename)
        fullfilename = "%s/%s" % (outdir, basename)
        if os.path.exists(fullfilename):
            print 'Error: %s already exists.' % fullfilename
            exit(2)
        mkdirp(os.path.dirname(fullfilename))
        open(fullfilename, "w").write(enc)
    else:
        print 'Skipping %s' % filename

if len(sys.argv) < 3:
    print 'Usage: %s <outdir> <infiles...>' % sys.argv[0]
    exit(1)

outdir = sys.argv[1]
if not os.path.isdir(outdir):
    os.mkdir(outdir)
for name in sys.argv[2:]:
    process(outdir, name)

print 'done'
