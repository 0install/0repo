# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from os.path import isabs

from zeroinstall import SafeException

def ensure_safe(rel_path):
	"""Ensure path is relative and doesn't contain '.', '..' or other hidden components."""
	if isabs(rel_path):
		raise SafeException("Feed path {path} not relative".format(path = rel_path))
	if rel_path.startswith(".") or "/." in rel_path:
		raise SafeException("Feed path {path} contains a dot-file component".format(path = rel_path))
	return rel_path

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
