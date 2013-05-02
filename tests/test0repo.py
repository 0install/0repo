import unittest
import tempfile
import shutil
import subprocess
import os, sys
import imp
from StringIO import StringIO

from os.path import join

from zeroinstall import SafeException
from zeroinstall.support import basedir
from zeroinstall.injector import qdom, model, gpg
from zeroinstall.injector.namespaces import XMLNS_IFACE

os.environ["http_proxy"] = "http://localhost:9999/bug"
mydir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath('..'))

test_gpghome = join(mydir, 'test-gpghome')

from repo.cmd import main
from repo import archives

gpg.ValidSig.is_trusted = lambda self, domain = None: True

def run_repo(args):
	oldcwd = os.getcwd()

	old_stdout = sys.stdout
	sys.stdout = StringIO()
	try:
		sys.stdin = StringIO('\n')	# (simulate a press of Return if needed)
		main(['0repo'] + args)
		return sys.stdout.getvalue()
	finally:
		os.chdir(oldcwd)
		sys.stdout = old_stdout

def update_config(old, new):
	if '0repo-config' in sys.modules:
		del sys.modules['0repo-config']

	with open('0repo-config.py') as stream:
		config_data = stream.read()

	with open('0repo-config.py', 'wt') as stream:
		new_data = config_data.replace(old, new)
		assert new_data != config_data
		stream.write(new_data)

	if os.path.exists('0repo-config.pyc'):
		os.unlink('0repo-config.pyc')

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

		os.environ['HOME'] = self.tmpdir

		for x in ['XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME']:
			if x in os.environ:
				del os.environ[x]
		for x in ['XDG_CONFIG_DIRS', 'XDG_CACHE_DIRS', 'XDG_DATA_DIRS']:
			os.environ[x] = ''

		if 'ZEROINSTALL_PORTABLE_BASE' in os.environ:
			del os.environ['ZEROINSTALL_PORTABLE_BASE']

		imp.reload(basedir)

	def tearDown(self):
		if '0repo-config' in sys.modules:
			del sys.modules['0repo-config']
		os.chdir("/")
		shutil.rmtree(self.tmpdir)

	def testSimple(self):
		# (do a slow sub-process call here just to check that the top-level
		# wrapper works)
		subprocess.check_call(['0repo', 'create', 'my-repo', 'Test Key for 0repo'])
		os.chdir('my-repo')

		update_config('raise Exception("No upload method specified: edit upload_archives() in 0repo-config.py")', 'pass')

		# Regenerate
		out = run_repo([])
		assert 'No .xml files in "incoming" directory (nothing to process)' in out, out
		assert os.path.exists(join('public', 'catalog.xml'))
		assert os.path.exists(join('public', 'resources/catalog.xsl'))
		assert os.path.exists(join('public', 'resources/catalog.css'))
		assert os.path.exists(join('public', 'keys', '6D66BDF4F467A18D.gpg'))

		# Create a new feed (external archive)
		shutil.copyfile(join(mydir, 'test-1.xml'), join('incoming', 'test-1.xml'))
		out = run_repo([])
		assert 'Processing test-1.xml' in out, repr(out)

		assert os.path.exists(join('feeds', 'tests', 'test.xml'))

		assert os.path.exists(join('public', 'tests', 'test.xml'))
		with open(join('public', 'tests', '6D66BDF4F467A18D.gpg')) as stream:
			data = stream.read()
			assert 'BEGIN PGP PUBLIC KEY BLOCK' in data, data

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
			stream, sigs = gpg.check_stream(stream)
			assert isinstance(sigs[0], gpg.ValidSig), sigs[0]

			stream.seek(0)

			feed = model.ZeroInstallFeed(qdom.parse(stream))
		impl2 = feed.implementations['sha1new=290eb133e146635fe37713fd58174324a16d595f']
		self.assertEqual(stored_archive.url, impl2.download_sources[0].url)

		# Check invalid feeds
		with open(join(mydir, 'test-1.xml'), 'rt') as stream:
			orig_data = stream.read()
		def test_invalid(xml):
			with open('test.xml', 'wt') as stream:
				stream.write(xml)
			try:
				run_repo(['add', 'test.xml'])
				assert 0, 'Not rejected'
			except SafeException as ex:
				return str(ex)

		ex = test_invalid(orig_data.replace('license', 'LICENSE'))
		assert "Missing 'license' attribute in" in ex, ex

		ex = test_invalid(orig_data.replace('released', 'RELEASED'))
		assert "Missing 'released' attribute in" in ex, ex

		ex = test_invalid(orig_data.replace('version="1"', 'version="1-pre"'))
		assert "Version number must end in a digit (got 1-pre)" in ex, ex

		# Import pre-existing feed
		update_config('CONTRIBUTOR_GPG_KEYS = None', 'CONTRIBUTOR_GPG_KEYS = set()')

		try:
			run_repo(['add', join(mydir, 'imported.xml')])
			assert 0
		except SafeException as ex:
			assert 'No trusted signatures on feed' in str(ex)

		update_config('CONTRIBUTOR_GPG_KEYS = set()', 'CONTRIBUTOR_GPG_KEYS = {"3F52282D484EB9401EE3A66A6D66BDF4F467A18D"}')

		out = run_repo(['add', join(mydir, 'imported.xml')])
		assert os.path.exists(join('public', 'tests', 'imported.xml'))


	def testRegister(self):
		out = run_repo(['create', 'my-repo', 'Test Key for 0repo'])
		assert not out
		os.chdir('my-repo')
		out = run_repo(['register'])
		assert 'http://example.com/myrepo/:' in out, out

		out = run_repo(['register'])
		assert "Already registered" in out, out

		os.chdir(mydir)
		out = run_repo(['add', 'test-1.xml'])
		assert "Updated public/tests/test.xml" in out, out

if __name__ == '__main__':
	unittest.main()
