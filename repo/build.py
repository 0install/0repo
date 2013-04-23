# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess, sys
from os.path import join, dirname, relpath
from xml.dom import minidom
import base64
from collections import namedtuple

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
	sig = "\n<!-- Base64 Signature\n" + encoded + "\n-->\n"
	return source_xml + sig

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

	return doc

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
						print("%s unchanged" % source_path)
						changed = False
				feeds.append(PublicFeed(target_path, new_doc, changed))

	for target_path, new_doc, changed in feeds:
		if not changed: continue

		path_to_resources = relpath(join('public', 'resources'), dirname(target_path))
		new_xml = (feed_header % path_to_resources) + new_doc.documentElement.toxml('utf-8')

		signed_xml = sign_xml(config, new_xml)

		target_dir = dirname(target_path)
		if not os.path.isdir(target_dir):
			os.makedirs(target_dir)

		with open(target_path + '.new', 'wb') as stream:
			stream.write(signed_xml)
		os.rename(target_path + '.new', target_path)
		print("Updated", target_path)

	return feeds
