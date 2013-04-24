# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from os.path import isabs
import os
import collections

from zeroinstall import SafeException

def ensure_dir(path):
	if not os.path.isdir(path):
		os.mkdir(path)

def group_by_target_url_dir(archives):
	results = collections.defaultdict(lambda: [])		# rel_url -> [basename]
	for archive in archives:
		results[archive.rel_url].append(archive.source_path)
	return results.items()

def ensure_safe(rel_path):
	"""Ensure path is relative and doesn't contain '.', '..' or other hidden components. Also,
	leading '-' is disallowed, as it may be confused with an option."""
	if isabs(rel_path):
		raise SafeException("Path {path} not relative".format(path = rel_path))
	if rel_path.startswith(".") or "/." in rel_path:
		raise SafeException("Path {path} contains a dot-file component".format(path = rel_path))
	if rel_path.startswith("-") or "/-" in rel_path:
		raise SafeException("A component in {path} starts with '-'".format(path = rel_path))
	return rel_path

# These are wrappers for the functions in config which perform some sanity checks on the results.

def get_feeds_rel_path(config, url):
	"""Return the relative path under "feeds" where we should store the feed with the given URL.
	@raise SafeException: url is not within this repository, or is otherwise malformed."""

	if not url.startswith(config.REPOSITORY_BASE_URL):
		raise SafeException("Feed URL '{url}' does not start with {base}".format(
			url = url,
			base = config.REPOSITORY_BASE_URL))
	
	uri_rel_path = url[len(config.REPOSITORY_BASE_URL):]
	feeds_rel_path = config.get_feeds_rel_path(uri_rel_path)
	if not feeds_rel_path.endswith('.xml'):
		raise SafeException("Feed relative path {path} must end in '.xml'".format(path = feeds_rel_path))
	return ensure_safe(feeds_rel_path)

def get_public_rel_path(config, feeds_rel_path):
	public_rel_path = config.get_public_rel_path(feeds_rel_path)
	return ensure_safe(public_rel_path)

def get_archive_rel_url(config, archive_basename, impl):
	rel_url = config.get_archive_rel_url(archive_basename, impl)
	return ensure_safe(rel_url)
