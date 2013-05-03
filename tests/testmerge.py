import sys, os, StringIO
from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall.injector import model, qdom
from zeroinstall.support import xmltools
import unittest
from xml.dom import minidom

ByteIO = StringIO.StringIO

sys.path.insert(0, '..')

from repo import merge, formatting

header = """<?xml version="1.0" ?>
<interface xmlns="http://zero-install.sourceforge.net/2004/injector/interface"
	   uri='http://test/hello.xml'>
  <name>test</name>
  <summary>for testing</summary>
  <description>This is for testing.</description>
  """
footer = """
</interface>
"""

def parse(xml):
	stream = ByteIO(xml)
	return model.ZeroInstallFeed(qdom.parse(stream))

def do_merge(master_xml, new_impl_path):
	# The tests were originally written for 0publish. This just adapts them to the new API.

	master_doc = minidom.parse(ByteIO(master_xml))
	with open(new_impl_path, 'rb') as stream:
		new_impl_doc = minidom.parse(stream)

	merge.merge(master_doc, new_impl_doc)

	return master_doc.toxml(encoding = 'utf-8')

def check_merge(master, new, expected):
	master_doc = minidom.parseString(header + master + footer)
	new_doc = minidom.parseString(header + new + footer)
	merge.merge(master_doc, new_doc)

	expected_doc = minidom.parseString(header + expected + footer)

	def remove_boring(doc):
		for node in list(doc.documentElement.childNodes):
			if node.localName in ('name', 'summary', 'description'):
				doc.documentElement.removeChild(node)
	remove_boring(master_doc)
	remove_boring(expected_doc)

	formatting.format_node(master_doc.documentElement, "\n")
	formatting.format_node(expected_doc.documentElement, "\n")

	master_doc.normalize()
	expected_doc.normalize()

	if xmltools.nodes_equal(master_doc.documentElement, expected_doc.documentElement):
		return

	actual = master_doc.documentElement.toxml()
	expected = expected_doc.documentElement.toxml()

	assert actual != expected

	raise Exception("Failed.\n\nExpected:\n{}\nActual:\n{}".format(expected, actual))

local_file = os.path.join(os.path.dirname(__file__), 'local.xml')
local_file_req = os.path.join(os.path.dirname(__file__), 'local-req.xml')
local_file_if = os.path.join(os.path.dirname(__file__), 'local-if.xml')
local_file_command = os.path.join(os.path.dirname(__file__), 'local-command.xml')
local_file_ns = os.path.join(os.path.dirname(__file__), 'local-ns.xml')
local_file_main_and_command = os.path.join(os.path.dirname(__file__), 'local-main-and-command.xml')
local_file_zi13 = os.path.join(os.path.dirname(__file__), 'zeroinstall-injector-1.3.xml')

def tap(s):
	print s
	return s

class TestMerge(unittest.TestCase):
	def testMergeFirst(self):
		master = parse(do_merge(header + footer, local_file))
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 1

	def testMergeSecond(self):
		master = parse(do_merge(header + "<implementation id='sha1=123' version='1'/>" + footer, local_file))
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2

	def testMergeTwice(self):
		try:
			once = do_merge(header + "<implementation id='sha1=123' version='1'/>" + footer, local_file)
			do_merge(once, local_file)
			assert 0
		except Exception as ex:
			assert 'Duplicate ID' in str(ex)

	def testMergeGroup(self):
		master = parse(do_merge(header + "<group>\n    <implementation id='sha1=123' version='1'/>\n  </group>" + footer, local_file))
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		assert master.implementations['sha1=002'].requires == []

	def testMergeLocalReq(self):
		master = parse(do_merge(header + "<group x='x'>\n    <implementation id='sha1=123' version='1'/>\n  </group>" + footer, local_file_req))
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		deps = master.implementations['sha1=003'].requires
		assert len(deps) == 1
		assert deps[0].interface == 'http://foo', deps[0]

		assert master.implementations['sha1=003'].metadata['http://mynamespace/foo bob'] == 'bob'

	def testNotSubset(self):
		master = parse(do_merge(header + "<group a='a'>\n    <implementation id='sha1=123' version='1'/>\n  </group>" + footer, local_file))
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		assert master.implementations['sha1=123'].metadata.get('a', None) == 'a'
		assert master.implementations['sha1=002'].metadata.get('a', None) == None

		master = parse(do_merge(header + """\n
  <group>
    <requires interface='http://foo' meta='foo'/>
    <implementation id='sha1=004' version='1'/>
  </group>
  <group>
    <requires interface='http://foo'>
      <version before='1'/>
    </requires>
    <implementation id='sha1=001' version='1'/>
  </group>""" + footer, local_file_req))
		assert len(master.implementations['sha1=001'].requires[0].restrictions) == 1
		assert len(master.implementations['sha1=003'].requires[0].restrictions) == 0

		assert master.implementations['sha1=004'].requires[0].metadata.get('meta', None) == 'foo'
		assert master.implementations['sha1=003'].requires[0].metadata.get('meta', None) == None

		assert master.implementations['sha1=003'].main == 'hello'

	def testMergeBest(self):
		master_xml = do_merge(header + """\n
  <group>
    <implementation id='sha1=123' version='1'/>
  </group>
  <group>
    <requires interface='http://foo'/>
    <implementation id='sha1=002' version='2'/>
  </group>""" + footer, local_file_req)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 3
		deps = master.implementations['sha1=003'].requires
		assert len(deps) == 1
		assert deps[0].interface == 'http://foo', deps[0]

		assert len(minidom.parseString(master_xml).documentElement.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 2

		# Again, but with the groups the other way around
		master_xml = do_merge(header + """\n
  <group>
    <requires interface='http://foo'/>
    <implementation id='sha1=002' version='2'/>
  </group>
  <group>
    <implementation id='sha1=123' version='1'/>
  </group>""" + footer, local_file_req)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 3
		deps = master.implementations['sha1=003'].requires
		assert len(deps) == 1
		assert deps[0].interface == 'http://foo', deps[0]

		assert len(minidom.parseString(master_xml).documentElement.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 2

	def testMergeBindings(self):
		check_merge("""\
<group>
  <binding foo='bar'/>
  <implementation id='sha1=123' version='1'/>
</group>""", """\
<group>
  <binding foo='bar'/>
  <implementation id='sha1=234' version='2'/>
</group>""", """\
<group>
  <binding foo="bar"/>
  <implementation id="sha1=123" version="1"/>
  <implementation id="sha1=234" version="2"/>
</group>""")

	def testMergeText(self):
		check_merge("""\
<group>
  <binding>One</binding>
  <implementation id='sha1=123' version='1'/>
</group>""", """\
<group>
  <binding>Two</binding>
  <implementation id='sha1=234' version='2'/>
</group>""", """\
<group>
  <binding>One</binding>
  <implementation id="sha1=123" version="1"/>
</group>
<group>
  <binding>Two</binding>
  <implementation id="sha1=234" version="2"/>
</group>""")

	def testMergeNS(self):
		master_xml = do_merge(header + footer, local_file_ns)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 1
		commands = master.implementations['sha1=003'].commands
		assert len(commands) == 1
		assert commands['run'].path == 'run.sh', commands['run'].path

		new_root = minidom.parseString(master_xml).documentElement
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 1
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'requires')) == 1
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'command')) == 1

		foo_test, = new_root.getElementsByTagNameNS('http://mynamespace/foo', 'test')
		foo1_test, = new_root.getElementsByTagNameNS('http://myother/foo', 'test')

	def testMergeCommand(self):
		# We create a new group inside this one, sharing the <requires> and adding the <command>
		master_xml = do_merge(header + """
  <group>
    <requires interface='http://foo'>
      <environment name='TESTING' value='true' mode='replace'/>
    </requires>
    <implementation id='sha1=002' version='2'/>
  </group>""" + footer, local_file_command)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		commands = master.implementations['sha1=003'].commands
		assert len(commands) == 1
		assert commands['run'].path == 'run.sh', commands['run'].path

		new_root = minidom.parseString(master_xml).documentElement
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 2
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'requires')) == 1
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'command')) == 1

		# We create a new top-level group inside this one, as we can't share the test command
		master_xml = do_merge(header + """
  <group>
    <requires interface='http://foo'>
      <environment name='TESTING' value='true' mode='replace'/>
    </requires>
    <command name='test' path='test.sh'/>
    <implementation id='sha1=002' version='2'/>
  </group>""" + footer, local_file_command)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		commands = master.implementations['sha1=003'].commands
		assert len(commands) == 1
		assert commands['run'].path == 'run.sh', commands['run'].path

		new_root = minidom.parseString(master_xml).documentElement
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 2
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'requires')) == 2
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'command')) == 2

		# We share the <requires> and override the <command>
		master_xml = do_merge(header + """
  <group>
    <requires interface='http://foo'>
      <environment name='TESTING' value='true' mode='replace'/>
    </requires>
    <command name='run' path='old-run.sh'/>
    <implementation id='sha1=002' version='2'/>
  </group>""" + footer, local_file_command)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		commands = master.implementations['sha1=003'].commands
		assert len(commands) == 1
		assert commands['run'].path == 'run.sh', commands['run'].path

		new_root = minidom.parseString(master_xml).documentElement
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 2
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'requires')) == 1
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'command')) == 2

		# We share the <requires> and the <command>
		master_xml = do_merge(header + """
  <group>
    <requires interface='http://foo'>
      <environment name='TESTING' value='true' mode='replace'/>
    </requires>
    <command name='run' path='run.sh'/>
    <implementation id='sha1=002' version='2'/>
  </group>""" + footer, local_file_command)
		master = parse(master_xml)
		assert master.url == 'http://test/hello.xml', master
		assert len(master.implementations) == 2
		commands = master.implementations['sha1=003'].commands
		assert len(commands) == 1
		assert commands['run'].path == 'run.sh', commands['run'].path

		new_root = minidom.parseString(master_xml).documentElement
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'group')) == 1
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'requires')) == 1
		assert len(new_root.getElementsByTagNameNS(XMLNS_IFACE, 'command')) == 1

	def testMerge2(self):
		master_xml = do_merge(header + """
  <group license="OSI Approved :: GNU Lesser General Public License (LGPL)" main="0launch">
    <command name="run" path="0launch">
      <runner interface="http://repo.roscidus.com/python/python">
	<version before="3"/>
      </runner>
    </command>

    <group>
      <command name="run" path="0launch"/>
      <implementation id="sha1new=7d1ecfbd76a42d56f029f9d0c72e4ac26c8561de" released="2011-07-23" version="1.2"/>
    </group>
  </group>
  """ + footer, local_file_zi13)
		doc = minidom.parseString(master_xml)

		n_groups = len(doc.getElementsByTagName("group"))
		assert n_groups == 2

	def testMergeMainAndCommand(self):
		# Ensure the main attribute doesn't get promoted over the command

		# Case 1: the group already has a suitable main and command.
		# We simply add the new implementation to the group, without its own main.
		master_xml = do_merge(header + """
  <group main='main'>
    <command name='run' path='run.sh'/>
    <implementation id="sha1=001" version="0.1"/>
  </group>
  """ + footer, local_file_main_and_command)
		feed = parse(master_xml)

		assert feed.implementations['sha1=001'].main == "run.sh"
		assert feed.implementations['sha1=002'].main == "run.sh"

		# Case 2: the group doesn't specify a main.
		# We need to create a sub-group for it.
		master_xml = do_merge(header + """
  <group>
    <command name='run' path='run.sh'/>
    <implementation id="sha1=001" version="0.1"/>
  </group>
  """ + footer, local_file_main_and_command)
		feed = parse(master_xml)

		assert feed.implementations['sha1=001'].main == "run.sh"
		assert feed.implementations['sha1=002'].main == "run.sh"

	def testMergeIf0installVersion(self):
		master_xml = do_merge(header + """
  <group>
    <command name='run' path='run.sh'/>
    <implementation id="sha1=004" version="0.4"/>
  </group>
  """ + footer, local_file_if)
		doc = minidom.parseString(master_xml)

		n_commands = len(doc.getElementsByTagName("command"))
		assert n_commands == 3

		# We can share the run-old.sh <command>
		master_xml = do_merge(header + """
  <group>
    <command name='run' path='run-old.sh' if-0install-version='..!2'/>
    <command name='run' path='run-mid.sh' if-0install-version='2..'/>
    <implementation id="sha1=004" version="0.4"/>
  </group>
  """ + footer, local_file_if)
		doc = minidom.parseString(master_xml)

		n_commands = len(doc.getElementsByTagName("command"))
		assert n_commands == 3

	def testLocalContext(self):
		def get_context(xml_frag):
			doc = minidom.parseString(header + xml_frag + footer)
			impls = list(doc.getElementsByTagNameNS(XMLNS_IFACE, 'implementation'))
			assert len(impls) == 1
			return merge.Context(impls[0])

		ctx = get_context("<implementation id='sha1=001' version='1'/>")
		assert ctx.attribs[(None, 'id')] == 'sha1=001'
		assert ctx.attribs[(None, 'version')] == '1'

		ctx = get_context("<group t='t' x='1' y:z='2' xmlns:y='yns'><implementation id='sha1=001' version='1' t='r'/></group>")
		assert ctx.attribs[(None, 'id')] == 'sha1=001'
		assert ctx.attribs[(None, 'version')] == '1'
		assert ctx.attribs[(None, 't')] == 'r'
		assert ctx.attribs[(None, 'x')] == '1'
		assert ctx.attribs[('yns', 'z')] == '2'

if __name__ == '__main__':
	unittest.main()
