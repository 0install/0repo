# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess, sys
from os.path import join, dirname, relpath, basename
from xml.dom import minidom, Node
import base64
from collections import namedtuple

from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall.support import xmltools
from zeroinstall import SafeException

from repo import paths

PublicFeed = namedtuple("PublicFeed", ["public_rel_path", "doc", "changed"])

feed_header = """<?xml version="1.0" ?>
<?xml-stylesheet type='text/xsl' href='%s/feed.xsl'?>
"""

def sign_xml(config, source_xml):
	child = subprocess.Popen(['gpg', '--detach-sign', '--default-key', config.GPG_SIGNING_KEY, '--use-agent', '--output', '-', '-'],
			stdin = subprocess.PIPE,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE)
	stdout, stderr = child.communicate(source_xml)
	exit_status = child.wait()
	if exit_status:
		raise SafeException("Error signing feed: %s" % stderr)
	if stderr:
		print(stderr, file=sys.stderr)

	encoded = base64.encodestring(stdout)
	sig = "<!-- Base64 Signature\n" + encoded + "\n-->\n"
	return source_xml + sig

def expand_impl_relative_urls(config, parent):
	for elem in parent.childNodes:
		if elem.nodeType != Node.ELEMENT_NODE: continue
		if elem.namespaceURI != XMLNS_IFACE: continue

		if elem.localName in ('archive', 'file'):
			archive = elem.getAttribute('href')
			assert archive
			if '/' not in archive:
				elem.setAttribute('href', config.archive_db.lookup(archive).url)
		elif elem.localName == 'recipe':
			expand_impl_relative_urls(config, elem)

def expand_relative_urls(config, parent):
	for elem in parent.childNodes:
		if elem.nodeType != Node.ELEMENT_NODE: continue
		if elem.namespaceURI != XMLNS_IFACE: continue

		if elem.localName == 'group':
			expand_relative_urls(config, elem)
		elif elem.localName == 'implementation':
			expand_impl_relative_urls(config, elem)

def generate_public_xml(config, source_xml_path):
	"""Load source_xml_path and expand any relative URLs."""
	with open(source_xml_path, 'rb') as stream:
		doc = minidom.parse(stream)

	root = doc.documentElement
	declared_iface = root.getAttribute('uri')
	if not declared_iface:
		raise SafeException("Feed '{path}' missing 'uri' attribute on root".format(path = source_xml_path))

	if not declared_iface.startswith(config.REPOSITORY_BASE_URL):
		raise SafeException("Feed '{path}' declares uri='{uri}', which is not under REPOSITORY_BASE_URL ({base})".format(
			path = source_xml_path,
			uri = declared_iface,
			base = config.REPOSITORY_BASE_URL))
	rel_uri = declared_iface[len(config.REPOSITORY_BASE_URL):]

	expected_path = join('feeds', config.get_feeds_rel_path(rel_uri))
	if expected_path != source_xml_path:
		raise SafeException("Feed '{path}' with uri='{uri}' should be located at '{expected_path}'".format(
			path = source_xml_path,
			uri = declared_iface,
			expected_path = expected_path))

	expand_relative_urls(config, root)

	return doc

def export_key(dir, signing_key):
	assert signing_key is not None

	paths.ensure_dir(dir)

	# Convert signing_key to key ID
	keyID = None
	keys_output = subprocess.check_output(['gpg', '--with-colons', '--list-keys', signing_key])
	for line in keys_output.split('\n'):
		parts = line.split(':')
		if parts[0] == 'pub':
			if keyID:
				raise Exception('Two key IDs returned from GPG!')
			keyID = parts[4]
	assert keyID, "Can't find GPG key '%s'" % signing_key

	key_file = os.path.join(dir, keyID + '.gpg')
	if not os.path.isfile(key_file):
		with open(key_file, 'w') as key_stream:
			subprocess.check_call(["gpg", "-a", "--export", signing_key], stdout = key_stream)
		print("Exported public key as '%s'" % key_file)
	return key_file

def build_public_feeds(config):
	feeds = []
	for dirpath, dirnames, filenames in os.walk('feeds'):
		for f in filenames:
			if f.endswith('.xml') and not f.startswith('.'):
				source_path = join(dirpath, f)
				target_path = join("public", paths.get_public_rel_path(config, relpath(source_path, 'feeds')))
				new_doc = generate_public_xml(config, source_path)
				changed = True
				if os.path.exists(target_path):
					with open(target_path, 'rb') as stream:
						old_doc = minidom.parse(stream)
					if xmltools.nodes_equal(old_doc.documentElement, new_doc.documentElement):
						#print("%s unchanged" % source_path)
						changed = False
				feeds.append(PublicFeed(target_path, new_doc, changed))

	key_path = export_key('keys', config.GPG_SIGNING_KEY)

	for target_path, new_doc, changed in feeds:
		target_dir = dirname(target_path)
		if not os.path.isdir(target_dir):
			os.makedirs(target_dir)

		if config.GPG_PUBLIC_KEY_DIRECTORY:
			key_symlink_path = join(target_dir, config.GPG_PUBLIC_KEY_DIRECTORY, basename(key_path))
			if not os.path.islink(key_symlink_path):
				os.symlink(relpath(key_path, dirname(key_symlink_path)), key_symlink_path)

		if not changed: continue

		path_to_resources = relpath(join('public', 'resources'), dirname(target_path))
		new_xml = (feed_header % path_to_resources).encode('utf-8') + new_doc.documentElement.toxml('utf-8') + '\n'

		signed_xml = sign_xml(config, new_xml)

		with open(target_path + '.new', 'wb') as stream:
			stream.write(signed_xml)
		os.rename(target_path + '.new', target_path)
		print("Updated", target_path)

	return feeds
