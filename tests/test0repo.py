import unittest
import tempfile
import shutil
import subprocess
import os, sys
from StringIO import StringIO

from os.path import join

from zeroinstall.injector import qdom
from zeroinstall.injector.namespaces import XMLNS_IFACE

os.environ["http_proxy"] = "http://localhost:9999/bug"
mydir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath('..'))

test_gpghome = join(mydir, 'test-gpghome')

from repo.cmd import main

def run_repo(args):
	old_stdout = sys.stdout
	sys.stdout = StringIO()
	try:
		main(['0repo'] + args)
		return sys.stdout.getvalue()
	finally:
		sys.stdout = old_stdout

class Test0Repo(unittest.TestCase):
	def setUp(self):
		self.tmpdir = tempfile.mkdtemp('-0repo')
		os.chdir(self.tmpdir)
		gpghome = join(self.tmpdir, 'gnupg')
		os.mkdir(gpghome)
		shutil.copyfile(join(test_gpghome, 'pubring.gpg'), join(gpghome, 'pubring.gpg'))
		shutil.copyfile(join(test_gpghome, 'secring.gpg'), join(gpghome, 'secring.gpg'))
		os.environ['GNUPGHOME'] = gpghome
		os.chmod(gpghome, 0o700)

	def tearDown(self):
		os.chdir("/")
		shutil.rmtree(self.tmpdir)
	
	def testSimple(self):
		# (do a slow sub-process call here just to check that the top-level
		# wrapper works)
		subprocess.check_call(['0repo', 'create', 'my-repo'])
		os.chdir('my-repo')

		with open('0repo-config.py') as stream:
			data = stream.read()
		data = data.replace('GPG_SIGNING_KEY = "0xDA9825AECAD089757CDABD8E07133F96CA74D8BA"',
			            'GPG_SIGNING_KEY = "0x3F52282D484EB9401EE3A66A6D66BDF4F467A18D"')
		with open('0repo-config.py', 'wt') as stream:
			stream.write(data)

		# Regenerate
		out = run_repo([])
		assert 'No .xml files in "incoming" directory (nothing to process)' in out, out
		assert os.path.exists(join('public', 'catalog.xml'))
		assert os.path.exists(join('public', 'catalog.xsl'))
		assert os.path.exists(join('public', 'catalog.css'))

		# Create a new feed (external archive)
		shutil.copyfile(join(mydir, 'test-1.xml'), join('incoming', 'test-1.xml'))
		out = run_repo([])
		assert 'Processing test-1.xml' in out, repr(out)

		assert os.path.exists(join('feeds', 'tests', 'test.xml'))

		assert os.path.exists(join('public', 'tests', 'test.xml'))

		with open(join('public', 'catalog.xml')) as stream:
			catalog = qdom.parse(stream)
		feeds = catalog.childNodes
		self.assertEqual(1, len(feeds))
		feed, = feeds
		self.assertEqual(XMLNS_IFACE, feed.uri)
		self.assertEqual("http://example.com/myrepo/tests/test.xml", feed.attrs['uri'])
	
if __name__ == '__main__':
	unittest.main()
