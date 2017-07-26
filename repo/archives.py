# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, shutil, hashlib, collections, re
from os.path import join, basename, dirname, abspath

from zeroinstall.injector import model
from zeroinstall import SafeException, support
from zeroinstall.support import tasks

from repo import paths, urltest

valid_simple_name = re.compile(r'^[^. \n/][^ \n/]*$')

class Archive(object):
	def __init__(self, source_path, rel_url, size, incoming_path = None):
		self.basename = basename(source_path)
		self.source_path = source_path
		self.rel_url = rel_url
		self.size = size
		self.incoming_path = incoming_path	# (used to delete from /incoming)

def get_sha1(path):
	sha1 = hashlib.sha1()
	with open(path, 'rb') as stream:
		while True:
			got = stream.read(4096)
			if not got: break
			sha1.update(got)
	return sha1.hexdigest()

def _assert_identical_archives(name, sha1, existing):
	if sha1 != existing.sha1:
		raise SafeException("A different archive with basename '{name}' is "
		                    "already in the repository: {archive}".format(name = name, archive = existing))


def _default_archive_test(archive, url):
	actual_size = urltest.get_size(url)
	if actual_size != archive.size:
		raise SafeException("Archive {url} has size {actual}, but expected {expected} bytes".format(
				    url = url, actual = actual_size, expected = archive.size))

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
			test_archive = getattr(config, 'check_external_archive', _default_archive_test)
			test_archive(step, archive)
			continue		# Hosted externally

		if not valid_simple_name.match(archive):
			raise SafeException("Illegal archive name '{name}'".format(name = archive))

		archive_path = join(incoming_dir, archive)
		if not os.path.isfile(archive_path):
			raise SafeException("Referenced upload '{path}' not found".format(path = archive_path))

		existing = config.archive_db.entries.get(archive, None)
		if existing is not None:
			new_sha1 = get_sha1(archive_path)
			_assert_identical_archives(archive, sha1=new_sha1, existing=existing)
		else:
			archive_rel_url = paths.get_archive_rel_url(config, archive, impl)

			# Copy to archives directory

			backup_dir = config.LOCAL_ARCHIVES_BACKUP_DIR	# note: may be relative; that's OK
			backup_target_dir = join(backup_dir, dirname(archive_rel_url))
			paths.ensure_dir(backup_target_dir)
			copy_path = join(backup_dir, archive_rel_url)
			shutil.copyfile(archive_path, copy_path)

			stored_archive = Archive(abspath(copy_path), archive_rel_url, step.size, archive_path)
			actual_size = os.path.getsize(stored_archive.source_path)
			if step.size != actual_size:
				raise SafeException("Archive '{archive}' has size '{actual}', but XML says size should be {expected}".format(
					archive = archive,
					actual = actual_size,
					expected = step.size))
			archives.append(stored_archive)

		step.url = os.path.abspath(archive_path)			# (just used below to test it)

	if not has_external_archives and getattr(config, 'CHECK_DIGESTS', True) and os.name != 'nt':
		# Check archives unpack to give the correct digests
		impl.feed.local_path = "/is-local-hack.xml"
		try:
			blocker = config.zconfig.fetcher.cook(required_digest, method,
						config.zconfig.stores, impl_hint = impl, dry_run = True, may_use_mirror = False)
			tasks.wait_for_blocker(blocker)
		finally:
			impl.feed.local_path = None

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
			self.save_all()

	def add(self, basename, url, sha1):
		existing = self.entries.get(basename, None)
		if existing is not None:
			_assert_identical_archives(basename, sha1=sha1, existing=existing)
		else:
			with open(self.path, 'at') as stream:
				stream.write('%s %s %s\n' % (basename, sha1, url))
			self.entries[basename] = StoredArchive(url, sha1)

	def lookup(self, basename):
		return self.entries.get(basename, None)
	
	def save_all(self):
		with open(self.path + '.new', 'wt') as stream:
			stream.write("# Records the absolute URL of all known archives.\n"
				     "# To relocate archives, edit this file to contain the new addresses and run '0repo'.\n"
				     "# Each line is 'basename SHA1 URL'\n")

			for basename, e in sorted(self.entries.items()):
				stream.write('%s %s %s\n' % (basename, e.sha1, e.url))
		support.portable_rename(self.path + '.new', self.path)

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
			raise SafeException("No <manifest-digest> given for '%(implementation)s' version %(version)s" %
					{'implementation': impl.feed.get_name(), 'version': impl.get_version()})
		raise SafeException("Unknown digest algorithms '%(algorithms)s' for '%(implementation)s' version %(version)s" %
				{'algorithms': impl.digests, 'implementation': impl.feed.get_name(), 'version': impl.get_version()})

	return required_digest

# Copy to archives directory and upload
def upload_archives(config, archives):
	config.upload_archives(archives)
	
	test_archive = getattr(config, 'check_uploaded_archive', _default_archive_test)

	for archive in archives:
		url = config.ARCHIVES_BASE_URL + archive.rel_url
		test_archive(archive, url)

	for archive in archives:
		sha1 = get_sha1(archive.source_path)
		config.archive_db.add(archive.basename, config.ARCHIVES_BASE_URL + archive.rel_url, sha1)

def process_archives(config, incoming_dir, feed):
	"""feed is the parsed XML being processed. Any archives are in 'incoming_dir'."""

	# Pick a digest to check (maybe we should check all of them?)
	# Find required archives and check they're in 'incoming'
	archives = []
	for impl in feed.implementations.values():
		required_digest = pick_digest(impl)
		for method in impl.download_sources:
			archives += process_method(config, incoming_dir, impl, method, required_digest)

	upload_archives(config, archives)

	return archives
