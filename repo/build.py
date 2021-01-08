# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.



import os, subprocess, sys
from os.path import join, dirname, relpath, basename, abspath
from xml.dom import minidom, Node
import base64
from collections import namedtuple

from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall.support import xmltools
from zeroinstall import SafeException, support

from repo import paths

PublicFeed = namedtuple("PublicFeed", ["source_path", "public_rel_path", "doc", "changed"])

feed_header = """<?xml version="1.0" ?>
<?xml-stylesheet type='text/xsl' href='%s/feed.xsl'?>
"""

def sign_xml(config, source_xml):
	if not config.GPG_SIGNING_KEY:
		return source_xml

	child = subprocess.Popen(['gpg', '--detach-sign', '--default-key', config.GPG_SIGNING_KEY, '--use-agent', '--output', '-', '-'],
			stdin = subprocess.PIPE,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE)
	stdout, stderr = child.communicate(source_xml)
	exit_status = child.wait()
	if exit_status:
		raise SafeException("Error signing feed: %s" % stderr)
	if stderr:
		print(stderr.decode().strip(), file=sys.stderr)

	encoded = base64.encodebytes(stdout)
	sig = b"<!-- Base64 Signature\n" + encoded + b"\n-->\n"
	return source_xml + sig

def import_missing_archive(config, impl, archive):
	from io import BytesIO
	from zeroinstall.injector import model, qdom
	from repo import archives
	print("Importing missing archive {name}".format(name = archive))
	doc = qdom.parse(BytesIO(impl.ownerDocument.documentElement.toxml('utf-8')))
	feed = model.ZeroInstallFeed(doc)
	impl = feed.implementations[impl.getAttribute('id')]
	required_digest = archives.pick_digest(impl)
	new_archives = []
	for method in impl.download_sources:
		new_archives += archives.process_method(config, 'incoming', impl, method, required_digest)
	archives.upload_archives(config, new_archives)
	for x in new_archives:
		os.unlink(x.incoming_path)
	return config.archive_db.lookup(archive)

def expand_impl_relative_urls(config, parent, impl):
	for elem in parent.childNodes:
		if elem.nodeType != Node.ELEMENT_NODE: continue
		if elem.namespaceURI != XMLNS_IFACE: continue

		if elem.localName in ('archive', 'file'):
			archive = elem.getAttribute('href')
			assert archive
			if '/' not in archive:
				x = config.archive_db.lookup(archive)
				if not x and os.path.exists(os.path.join('incoming', archive)):
					x = import_missing_archive(config, impl, archive)
				if not x:
					raise SafeException("Missing entry for {basename} in {db}; can't build feeds."
							    "Place missing archives in 'incoming' and try again.".format(
						basename = archive,
						db = config.archive_db.path))
				elem.setAttribute('href', x.url)
		elif elem.localName == 'recipe':
			expand_impl_relative_urls(config, elem, impl = impl)

def expand_relative_urls(config, parent):
	for elem in parent.childNodes:
		if elem.nodeType != Node.ELEMENT_NODE: continue
		if elem.namespaceURI != XMLNS_IFACE: continue

		if elem.localName == 'group':
			expand_relative_urls(config, elem)
		elif elem.localName == 'implementation':
			expand_impl_relative_urls(config, elem, impl = elem)

def generate_public_xml(config, source_xml_path):
	"""Load source_xml_path and expand any relative URLs."""
	try:
		with open(source_xml_path, 'rb') as stream:
			doc = minidom.parse(stream)
	except:
		print("Failed to process %s" % (source_xml_path))
		raise

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
	keys_output = subprocess.check_output(['gpg', '--with-colons', '--list-keys', signing_key], encoding='utf-8')
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
				public_rel_path = paths.get_public_rel_path(config, relpath(source_path, 'feeds'))
				target_path = join("public", public_rel_path)
				new_doc = generate_public_xml(config, source_path)
				changed = True
				if os.path.exists(target_path):
					with open(target_path, 'rb') as stream:
						old_doc = minidom.parse(stream)
					if xmltools.nodes_equal(old_doc.documentElement, new_doc.documentElement):
						#print("%s unchanged" % source_path)
						changed = False
				feeds.append(PublicFeed(abspath(source_path), public_rel_path, new_doc, changed))

	if config.GPG_SIGNING_KEY:
		key_path = export_key(join('public', 'keys'), config.GPG_SIGNING_KEY)
		other_files = [relpath(key_path, 'public')]
	else:
		other_files = []

	for public_feed in feeds:
		target_path = join('public', public_feed.public_rel_path)

		target_dir = dirname(target_path)
		if not os.path.isdir(target_dir):
			os.makedirs(target_dir)

		if config.GPG_SIGNING_KEY and config.GPG_PUBLIC_KEY_DIRECTORY:
			key_symlink_rel_path = join(dirname(public_feed.public_rel_path), config.GPG_PUBLIC_KEY_DIRECTORY, basename(key_path))
			other_files.append(key_symlink_rel_path)
			key_symlink_path = join('public', key_symlink_rel_path)
			if not os.path.exists(key_symlink_path):
				if os.name == 'nt':
					import shutil
					shutil.copyfile(key_path, key_symlink_path)
				else:
					os.symlink(relpath(key_path, dirname(key_symlink_path)), key_symlink_path)
			os.stat(key_symlink_path)

		if not public_feed.changed: continue

		path_to_resources = relpath(join('public', 'resources'), dirname(target_path)).replace(os.sep, '/')
		new_xml = (feed_header % path_to_resources).encode('utf-8') + public_feed.doc.documentElement.toxml('utf-8') + b'\n'

		signed_xml = sign_xml(config, new_xml)

		with open(target_path + '.new', 'wb') as stream:
			stream.write(signed_xml)
		support.portable_rename(target_path + '.new', target_path)
		print("Updated", target_path)

	return feeds, other_files
