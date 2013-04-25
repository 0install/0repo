# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, shutil, hashlib, collections
from os.path import join, dirname, basename, abspath

from zeroinstall.injector.handler import Handler
from zeroinstall.injector import model, fetch
from zeroinstall import SafeException
from zeroinstall.support import tasks
from zeroinstall.zerostore import Store

from repo import paths

class Archive(object):
	def __init__(self, basename, rel_url):
		self.basename = basename
		self.source_path = abspath(join("incoming", self.basename))
		self.rel_url = rel_url

class TestStores:
	stores = [Store("/tmp/")]

class TestConfig:
	def __init__(self):
		self.handler = Handler()
		self.stores = TestStores()

class TestScheduler:
	@tasks.async
	def download(self, dl, timeout = None):
		yield
		with open(join('incoming', basename(dl.url)), 'rb') as stream:
			shutil.copyfileobj(stream, dl.tempfile)

class TestFetcher(fetch.Fetcher):
	def __init__(self):
		fetch.Fetcher.__init__(self, TestConfig())

	scheduler = TestScheduler()

def get_sha1(path):
	sha1 = hashlib.sha1()
	with open(path, 'rb') as stream:
		while True:
			got = stream.read(4096)
			if not got: break
			sha1.update(got)
	return sha1.hexdigest()

def process_method(config, impl, method):
	archives = []

	if not isinstance(method, model.Recipe):
		# turn an individual method into a single-step Recipe
		step = method
		method = model.Recipe()
		method.steps.append(step)

	has_external_archives = False

	for step in method.steps:
		if not hasattr(step, 'url'): continue
		archive = step.url

		if '/' in archive:
			has_external_archives = True
			continue		# Hosted externally

		if archive.startswith('.'):
			raise SafeException("Archive name {name} starts with '.'".format(name = archive))

		if ':' in archive:
			raise SafeException("Archive name {name} contains ':'".format(name = archive))

		if not os.path.isfile(join('incoming', archive)):
			raise SafeException("Referenced upload '{name}' not found in 'incoming' directory".format(name = archive))

		existing = config.archive_db.entries.get(archive, None)
		if existing is not None:
			new_sha1 = get_sha1(join('incoming', archive))
			if new_sha1 != existing.sha1:
				raise SafeException("A different archive with basename '{name}' is "
						    "already in the repository: {archive}".format(name = archive, archive = existing))
			step.url = existing.url
		else:
			archive_rel_url = paths.get_archive_rel_url(config, archive, impl)
			stored_archive = Archive(archive, archive_rel_url)
			actual_size = os.path.getsize(stored_archive.source_path)
			if step.size != actual_size:
				raise SafeException("Archive '{archive}' has size '{actual}', but XML says size should be {expected}".format(
					archive = archive,
					actual = actual_size,
					expected = step.size))
			archives.append(stored_archive)

			step.url = config.ARCHIVES_BASE_URL + archive_rel_url	# (just used below to test it)

	if not has_external_archives:
		# Check archives unpack to give the correct digests
		fetcher = TestFetcher()

		blocker = fetcher.cook(impl.id, method, fetcher.config.stores, dry_run = True, may_use_mirror = False)
		tasks.wait_for_blocker(blocker)
	# should we download external archives and test them too?

	return archives

StoredArchive = collections.namedtuple('StoredArchive', ['url', 'sha1'])

class ArchiveDB:
	def __init__(self, path):
		self.path = abspath(path)
		self.entries = {}
		if os.path.exists(path):
			with open(path, 'rt') as stream:
				for line in stream:
					line = line.strip()
					if line.startswith('#') or not line:
						continue
					key, sha1, url = [x.strip() for x in line.split(' ', 2)]
					assert key not in self.entries, key
					self.entries[key] = StoredArchive(url, sha1)
		else:
			with open(path, 'wt') as stream:
				stream.write("# Records the absolute URL of all known archives.\n"
					     "# To relocate archives, edit this file to contain the new addresses and run '0repo'.\n"
					     "# Each line is 'basename SHA1 URL'\n")

	def add(self, basename, url, sha1):
		assert basename not in self.entries, basename
		with open(self.path, 'at') as stream:
			stream.write('%s %s %s\n' % (basename, sha1, url))
		self.entries[basename] = StoredArchive(url, sha1)

	def lookup(self, basename):
		x = self.entries.get(basename, None)
		if x:
			return x
		raise SafeException("Missing entry for {basename} in {db}; can't build feeds.".format(
			basename = basename,
			db = self.path))

def process_archives(config, feed):
	"""feed is the parsed XML in the incoming directory."""

	# Find required archives and check they're in 'incoming'
	archives = []
	for impl in feed.implementations.values():
		for method in impl.download_sources:
			archives += process_method(config, impl, method)

	# Upload archives
	config.upload_archives(archives)

	# Test uploads
	# TODO

	for archive in archives:
		sha1 = get_sha1(archive.source_path)
		config.archive_db.add(archive.basename, config.ARCHIVES_BASE_URL + archive.rel_url, sha1)

	return archives

def finish_archives(config, archives):
	# Move archives to backup dir (or delete if LOCAL_ARCHIVES_BACKUP_DIR not set)

	backup_dir = config.LOCAL_ARCHIVES_BACKUP_DIR
	if backup_dir is not None:
		# (note: may be relative; that's OK)
		paths.ensure_dir(backup_dir)

	for archive in archives:
		assert archive.basename in config.archive_db.entries, archive

		if backup_dir is None:
			os.unlink(archive.source_path)
		else:
			backup_target_dir = join(backup_dir, dirname(archive.rel_url))
			paths.ensure_dir(backup_target_dir)
			os.rename(archive.source_path, join(backup_target_dir, archive.basename))
