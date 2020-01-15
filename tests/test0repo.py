import unittest
import tempfile
import shutil
import subprocess
import os, sys
import imp
import builtins
from io import StringIO

from os.path import join

from zeroinstall import SafeException
from zeroinstall.support import basedir, ro_rmtree
from zeroinstall.injector import qdom, model, gpg
from zeroinstall.injector.namespaces import XMLNS_IFACE

os.environ["http_proxy"] = "http://localhost:9999/bug"
mydir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath('..'))

test_gpghome = join(mydir, 'test-gpghome')

from repo.cmd import main
from repo import archives, registry, paths, urltest

responses = {}		# Path -> Response

class FakeResponse:
	status = 200

	def __init__(self, size):
		self.size = size
		if size < 0:
			self.status = 404

	def getheader(self, name):
		assert name == 'Content-Length', name
		return str(self.size)

	def close(self):
		pass

class TestAPI:
	@staticmethod
	def upload(archives):
		for archive in archives:
			if 'INVALID' not in archive.rel_url:
				responses['/myrepo/archives/' + archive.rel_url] = FakeResponse(archive.size)

builtins.test0repo = TestAPI

class FakeHttpLib:
	class HTTPConnection:
		def __init__(self, host, port):
			pass

		def request(self, method, path, headers):
			assert method == 'HEAD'
			self.path = path

		def getresponse(self):
			return responses.get(self.path, FakeResponse(-1))

urltest.httplib = FakeHttpLib()
urltest.ftplib = None

gpg.ValidSig.is_trusted = lambda self, domain = None: True

def run_repo(args, stdin = ''):
	oldcwd = os.getcwd()

	old_stdout = sys.stdout
	sys.stdout = StringIO()
	try:
		sys.stdin = StringIO(stdin + '\n')	# (simulate pressing Return if needed)
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

def test_invalid(xml):
	with open('test.xml', 'wt') as stream:
		stream.write(xml)
	try:
		run_repo(['add', 'test.xml'])
		assert 0, 'Not rejected'
	except SafeException as ex:
		return str(ex)

class Test0Repo(unittest.TestCase):
	def setUp(self):
		self.tmpdir = tempfile.mkdtemp('-0repo')
		os.chdir(self.tmpdir)
		gpghome = join(self.tmpdir, 'gnupg')
		shutil.copytree(test_gpghome, gpghome)
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

		responses.clear()

	def tearDown(self):
		if '0repo-config' in sys.modules:
			del sys.modules['0repo-config']
		os.chdir("/")
		ro_rmtree(self.tmpdir)

	def testSimple(self):
		# (do a slow sub-process call here just to check that the top-level
		# wrapper works)
		subprocess.check_call(['0repo', 'create', 'my-repo', 'Test Key for 0repo'])
		os.chdir('my-repo')

		update_config('raise Exception("No upload method specified: edit upload_archives() in 0repo-config.py")',
				'return test0repo.upload(archives)')

		# Regenerate
		out = run_repo([])
		assert "Exported public key as 'public/keys/6D66BDF4F467A18D.gpg'" in out, out
		assert os.path.exists(join('public', 'catalog.xml'))
		assert os.path.exists(join('public', 'resources/catalog.xsl'))
		assert os.path.exists(join('public', 'resources/catalog.css'))
		assert os.path.exists(join('public', 'keys', '6D66BDF4F467A18D.gpg'))

		# Create a new feed (external archive)
		shutil.copyfile(join(mydir, 'test-1.xml'), join('incoming', 'test-1.xml'))
		responses['/downloads/test-1.tar.bz2'] = FakeResponse(419419)
		out = run_repo([])
		assert 'Processing test-1.xml' in out, repr(out)

		assert os.path.exists(join('feeds', 'tests', 'test.xml'))

		assert os.path.exists(join('public', 'tests', 'test.xml'))
		with open(join('public', 'tests', '6D66BDF4F467A18D.gpg')) as stream:
			data = stream.read()
			assert 'BEGIN PGP PUBLIC KEY BLOCK' in data, data

		with open(join('public', 'catalog.xml'), 'rb') as stream:
			catalog = qdom.parse(stream)
		feeds = catalog.childNodes
		self.assertEqual(1, len(feeds))
		feed, = feeds
		self.assertEqual(XMLNS_IFACE, feed.uri)
		self.assertEqual("http://example.com/myrepo/tests/test.xml", feed.attrs['uri'])

		# Check invalid archives are rejected
		with open(join(mydir, 'test-2.xml'), 'rt') as stream:
			test2_orig = stream.read()
		ex = test_invalid(test2_orig.replace('href="test-2.tar.bz2"', 'href=""'))
		assert "Missing href attribute on <archive>" in ex, ex

		ex = test_invalid(test2_orig.replace('href="test-2.tar.bz2"', 'href=".tar.bz2"'))
		assert ex == "Illegal archive name '.tar.bz2'", ex

		ex = test_invalid(test2_orig.replace('href="test-2.tar.bz2"', 'href="foo bar"'))
		assert ex == "Illegal archive name 'foo bar'", ex

		ex = test_invalid(test2_orig.replace('href="test-2.tar.bz2"', 'href="foo&#xa;bar"'))
		assert ex == "Illegal archive name 'foo\nbar'", ex

		ex = test_invalid(test2_orig)
		assert "test-2.tar.bz2' not found" in ex, ex

		ex = test_invalid(test2_orig.replace('href="test-2.tar.bz2"', 'href="http://example.com/INVALID"'))
		assert "HTTP error: got status code 404" in ex, ex

		shutil.copyfile(join(mydir, 'test-2.tar.bz2'), 'test-2.tar.bz2')

		ex = test_invalid(test2_orig.replace("sha256new='RPUJPV", "sha256new='RPV"))
		assert 'Incorrect manifest -- archive is corrupted' in ex, ex

		# Now add some local archives
		shutil.copyfile(join(mydir, 'test-2.tar.bz2'), join('incoming', 'test-2.tar.bz2'))
		shutil.copyfile(join(mydir, 'test-2.xml'), join('incoming', 'test-2.xml'))
		out = run_repo([], stdin = 'n\n')		# (don't mark 0.1 as stable)
		assert 'Updated public/tests/test.xml' in out, out

		self.assertEqual([], os.listdir('incoming'))
		assert os.path.exists(join('archive-backups', 'test-2.tar.bz2'))

		archive_db = archives.ArchiveDB('archives.db')
		stored_archive = archive_db.lookup('test-2.tar.bz2')
		self.assertEqual('852dda97d7c67e055738de87c27df85c4b6e5707', stored_archive.sha1)
		self.assertEqual('http://example.com/myrepo/archives/test-2.tar.bz2', stored_archive.url)

		with open(join('public', 'tests', 'test.xml'), 'rb') as stream:
			stream, sigs = gpg.check_stream(stream)
			assert isinstance(sigs[0], gpg.ValidSig), sigs[0]

			stream.seek(0)

			feed = model.ZeroInstallFeed(qdom.parse(stream))
		impl2 = feed.implementations['version2']
		self.assertEqual(stored_archive.url, impl2.download_sources[0].url)

		# Check invalid feeds
		with open(join(mydir, 'test-1.xml'), 'rt') as stream:
			orig_data = stream.read()

		ex = test_invalid(orig_data.replace('license', 'LICENSE'))
		assert "Missing 'license' attribute in" in ex, ex

		ex = test_invalid(orig_data.replace('released', 'RELEASED'))
		assert "Missing 'released' attribute in" in ex, ex

		ex = test_invalid(orig_data.replace('version="1"', 'version="1-pre"'))
		assert "Version number must end in a digit (got 1-pre)" in ex, ex

		# Import twice with identical XML
		out = run_repo(['add', join(mydir, 'test-2.xml')])
		assert 'Already merged this into feeds/tests/test.xml; skipping' in out, out

		# Import twice with non-identical XML
		ex = test_invalid(orig_data.replace('only', 'ONLY'))
		assert 'Duplicate ID sha1new=4f860b217bb94723ad6af9062d25dc7faee6a7ae' in ex, ex

		# Re-add the same archive
		with open('test.xml', 'wt') as stream:
			stream.write(test2_orig.replace('version2', 'version3').replace('version="2"', 'version="3"'))
		out = run_repo(['add', 'test.xml'], stdin='y\n')	# (mark 0.2 as stable)
		assert 'Updated public/tests/test.xml' in out, out
		assert "The previous release, version 2, is still marked as 'testing'. Set to stable?" in out, out

		# Re-add a different archive
		with open('test-2.tar.bz2', 'ab') as stream:
			stream.write(b'!')
		ex = test_invalid(test2_orig.replace('version2', 'version4'))
		assert "A different archive with basename 'test-2.tar.bz2' is already in the repository" in ex, ex

		# Test a recipe
		out = run_repo(['add', join(mydir, 'test-4.xml')], stdin = 'n\n')
		assert "Updated public/tests/test.xml" in out, out

		# Import pre-existing feed
		update_config('CONTRIBUTOR_GPG_KEYS = None', 'CONTRIBUTOR_GPG_KEYS = set()')

		try:
			run_repo(['add', join(mydir, 'imported.xml')])
			assert 0
		except SafeException as ex:
			assert 'No trusted signatures on feed' in str(ex)

		update_config('CONTRIBUTOR_GPG_KEYS = set()', 'CONTRIBUTOR_GPG_KEYS = {"3F52282D484EB9401EE3A66A6D66BDF4F467A18D"}')

		responses['/imported-1.tar.bz2'] = FakeResponse(200)
		out = run_repo(['add', join(mydir, 'imported.xml')])
		assert os.path.exists(join('public', 'tests', 'imported.xml'))

		# Update stability
		out = run_repo(['modify', 'http://example.com/myrepo/tests/test.xml', '4', '--stability=buggy'])
		assert 'Updated public/tests/test.xml' in out, out

		# Check stability levels
		with open(join('public', 'tests', 'test.xml'), 'rb') as stream:
			stream, sigs = gpg.check_stream(stream)
			assert isinstance(sigs[0], gpg.ValidSig), sigs[0]
			stream.seek(0)
			feed = model.ZeroInstallFeed(qdom.parse(stream))
		self.assertEqual(model.testing, feed.implementations["sha1new=4f860b217bb94723ad6af9062d25dc7faee6a7ae"].get_stability())
		self.assertEqual(model.stable, feed.implementations['version2'].get_stability())
		self.assertEqual(model.testing, feed.implementations['version3'].get_stability())
		self.assertEqual(model.buggy, feed.implementations['version4'].get_stability())

	def testRegister(self):
		self.assertEqual(None, registry.lookup("http://example.com/myrepo/foo.xml", missing_ok = True))

		out = run_repo(['create', 'my-repo', 'Test Key for 0repo'])
		assert not out
		os.chdir('my-repo')
		out = run_repo(['register'])
		assert 'http://example.com/myrepo/:' in out, out

		out = run_repo(['register'])
		assert "Already registered" in out, out

		os.chdir(mydir)
		responses['/downloads/test-1.tar.bz2'] = FakeResponse(419419)
		out = run_repo(['add', 'test-1.xml'])
		assert "Updated public/tests/test.xml" in out, out

		reg = registry.lookup("http://example.com/myrepo/foo.xml")
		assert reg['type'] == 'local'

		try:
			reg = registry.lookup("http://example.com/notmyrepo/foo.xml")
			assert 0
		except SafeException as ex:
			assert 'No registered repository for' in str(ex), ex

	def testReindex(self):
		out = run_repo(['create', 'my-repo', 'Test Key for 0repo'])
		assert not out
		os.chdir('my-repo')
		update_config('raise Exception("No upload method specified: edit upload_archives() in 0repo-config.py")',
				'return test0repo.upload(archives)')

		out = run_repo(['add', join(mydir, 'test-2.xml')])
		assert 'Updated public/tests/test.xml' in out, out

		out = run_repo(['reindex'])
		assert 'No changes found' in out, out

		os.unlink('archives.db')

		out = run_repo(['reindex'])
		assert 'test-2.tar.bz2: added to database: http://example.com/myrepo/archives/test-2.tar.bz2' in out, out

		os.mkdir(join("archive-backups", "subdir"))
		os.rename(join("archive-backups", "test-2.tar.bz2"),
			  join("archive-backups", "subdir", "test-2.tar.bz2"))

		out = run_repo(['reindex'])
		assert 'New URL: http://example.com/myrepo/archives/subdir/test-2.tar.bz2' in out, out
		assert 'Old database saved as' in out, out
		assert '(changes: 1)' in out, out
		assert "Run '0repo update' to update public feeds." in out, out

		out = run_repo(['update'])
		assert 'Updated public/tests/test.xml' in out, out

	def testGrouping(self):
		a = archives.Archive('/tmp/a.tgz', 'a.tgz', 0)
		b = archives.Archive('/tmp/b.tgz', 'foo/sub/b.tgz', 0)
		c = archives.Archive('/tmp/c.tgz', 'foo/sub/c.tgz', 0)
		groups = {d: fs for d, fs in paths.group_by_target_url_dir([a, b, c])}
		self.assertEqual(['', 'foo/sub'], sorted(groups))
		self.assertEqual(['/tmp/a.tgz'], sorted(groups['']))
		self.assertEqual(['/tmp/b.tgz', '/tmp/c.tgz'], sorted(groups['foo/sub']))

if __name__ == '__main__':
	unittest.main()
