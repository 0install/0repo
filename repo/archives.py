# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, shutil, hashlib, collections, re
from os.path import join, basename, dirname, abspath

from zeroinstall.injector.handler import Handler
from zeroinstall.injector import model, fetch
from zeroinstall import SafeException
from zeroinstall.support import tasks
from zeroinstall.zerostore import Store

from repo import paths

valid_simple_name = re.compile(r'^[^. \n/][^ \n/]*$')

class Archive(object):
	def __init__(self, source_path, rel_url):
		self.basename = basename(source_path)
		self.source_path = source_path
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
		assert dl.url.startswith("http://example.com/")
		path = dl.url[len("http://example.com/"):]
		with open(path, 'rb') as stream:
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

def process_method(config, incoming_dir, impl, method, required_digest):
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

		if not valid_simple_name.match(archive):
			raise SafeException("Illegal archive name '{name}'".format(name = archive))

		archive_path = join(incoming_dir, archive)
		if not os.path.isfile(archive_path):
			raise SafeException("Referenced upload '{path}' not found".format(path = archive_path))

		existing = config.archive_db.entries.get(archive, None)
		if existing is not None:
			new_sha1 = get_sha1(archive_path)
			if new_sha1 != existing.sha1:
				raise SafeException("A different archive with basename '{name}' is "
						    "already in the repository: {archive}".format(name = archive, archive = existing))
		else:
			archive_rel_url = paths.get_archive_rel_url(config, archive, impl)
			stored_archive = Archive(archive_path, archive_rel_url)
			actual_size = os.path.getsize(stored_archive.source_path)
			if step.size != actual_size:
				raise SafeException("Archive '{archive}' has size '{actual}', but XML says size should be {expected}".format(
					archive = archive,
					actual = actual_size,
					expected = step.size))
			archives.append(stored_archive)

		step.url = "http://example.com/" + archive_path	# (just used below to test it)

	if not has_external_archives:
		# Check archives unpack to give the correct digests
		fetcher = TestFetcher()

		blocker = fetcher.cook(required_digest, method, fetcher.config.stores, dry_run = True, may_use_mirror = False)
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

def pick_digest(impl):
	from zeroinstall.zerostore import manifest, parse_algorithm_digest_pair
	best = None
	for digest in impl.digests:
		alg_name, digest_value = parse_algorithm_digest_pair(digest)
		alg = manifest.algorithms.get(alg_name, None)
		if alg and (best is None or best.rating < alg.rating):
			best = alg
			required_digest = digest

	if best is None:
		if not impl.digests:
			raise SafeException(_("No <manifest-digest> given for '%(implementation)s' version %(version)s") %
					{'implementation': impl.feed.get_name(), 'version': impl.get_version()})
		raise SafeException(_("Unknown digest algorithms '%(algorithms)s' for '%(implementation)s' version %(version)s") %
				{'algorithms': impl.digests, 'implementation': impl.feed.get_name(), 'version': impl.get_version()})

	return required_digest

def process_archives(config, incoming_dir, feed):
	"""feed is the parsed XML being processed. Any archives are in 'incoming_dir'."""

	# Pick a digest to check (maybe we should check all of them?)
	# Find required archives and check they're in 'incoming'
	archives = []
	for impl in feed.implementations.values():
		required_digest = pick_digest(impl)
		for method in impl.download_sources:
			archives += process_method(config, incoming_dir, impl, method, required_digest)

	# Upload archives
	config.upload_archives(archives)

	# Test uploads
	# TODO

	for archive in archives:
		sha1 = get_sha1(archive.source_path)
		config.archive_db.add(archive.basename, config.ARCHIVES_BASE_URL + archive.rel_url, sha1)

	return archives

def finish_archives(config, archives, delete):
	# Copy archives to backup dir if LOCAL_ARCHIVES_BACKUP_DIR is set.
	# Then delete (if delete is True).

	backup_dir = config.LOCAL_ARCHIVES_BACKUP_DIR
	if backup_dir is not None:
		# (note: may be relative; that's OK)
		paths.ensure_dir(backup_dir)

	for archive in archives:
		assert archive.basename in config.archive_db.entries, archive

		if backup_dir is None:
			if delete:
				os.unlink(archive.source_path)
		else:
			backup_target_dir = join(backup_dir, dirname(archive.rel_url))
			paths.ensure_dir(backup_target_dir)
			if delete:
				os.rename(archive.source_path, join(backup_target_dir, archive.basename))
			else:
				shutil.copyfile(archive.source_path, join(backup_target_dir, archive.basename))
