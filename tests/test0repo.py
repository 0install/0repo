import unittest
import tempfile
import shutil
import subprocess
import os, sys
from StringIO import StringIO

from os.path import join

from zeroinstall.injector import qdom, model
from zeroinstall.injector.namespaces import XMLNS_IFACE

os.environ["http_proxy"] = "http://localhost:9999/bug"
mydir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath('..'))

test_gpghome = join(mydir, 'test-gpghome')

from repo.cmd import main
from repo import archives

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
		data = data.replace('GPG_SIGNING_KEY = "0x2E32123D8BE241A3B6D91E0301685F11607BB2C5"',
			            'GPG_SIGNING_KEY = "0x3F52282D484EB9401EE3A66A6D66BDF4F467A18D"')
		data = data.replace('raise Exception("No upload method specified: edit upload_archives() in 0repo-config.py")',
			            'pass')
		with open('0repo-config.py', 'wt') as stream:
			stream.write(data)

		# Regenerate
		out = run_repo([])
		assert 'No .xml files in "incoming" directory (nothing to process)' in out, out
		assert os.path.exists(join('public', 'catalog.xml'))
		assert os.path.exists(join('public', 'resources/catalog.xsl'))
		assert os.path.exists(join('public', 'resources/catalog.css'))

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

		# Now add some local archives
		shutil.copyfile(join(mydir, 'test-2.xml'), join('incoming', 'test-2.xml'))
		shutil.copyfile(join(mydir, 'test-2.tar.bz2'), join('incoming', 'test-2.tar.bz2'))
		out = run_repo([])

		self.assertEqual([], os.listdir('incoming'))
		assert os.path.exists(join('archives', 'test-2.tar.bz2'))

		archive_db = archives.ArchiveDB('archives.db')
		stored_archive = archive_db.lookup('test-2.tar.bz2')
		self.assertEqual('852dda97d7c67e055738de87c27df85c4b6e5707', stored_archive.sha1)
		self.assertEqual('http://example.com/myrepo/archives/test-2.tar.bz2', stored_archive.url)

		with open(join('public', 'tests', 'test.xml'), 'rb') as stream:
			feed = model.ZeroInstallFeed(qdom.parse(stream))
		impl2 = feed.implementations['sha1new=290eb133e146635fe37713fd58174324a16d595f']
		self.assertEqual(stored_archive.url, impl2.download_sources[0].url)
	
if __name__ == '__main__':
	unittest.main()
