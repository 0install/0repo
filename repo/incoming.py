# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess
from io import BytesIO
from os.path import join, dirname, basename, relpath
from xml.dom import minidom, Node

from zeroinstall.injector import qdom, model, gpg
from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall import SafeException, support

from repo import paths, archives, scm, merge, formatting

def get_feed_url(root, path):
	uri = root.attrs.get('uri', None)
	if uri is not None:
		return uri

	for child in root.childNodes:
		if child.name == 'feed-for' and child.uri == XMLNS_IFACE:
			# TODO: This actually gives us the interface. We currently assume we're adding to the
			# default feed for the interface, which is wrong. If there is a 'feed' attribute on the
			# <feed-for>, we should use that instead. This will also require updating 0publish.
			master = child.attrs['interface']
			return master
	else:
		raise SafeException("Missing <feed-for>/uri in " + path)

def get_last_commit(feed_path):
	"""Get the (subject, XML) of the last commit."""
	return subprocess.check_output(['git', 'log', '-n', '1', '--pretty=format:%s%n%b', '--', feed_path], cwd = 'feeds').split('\n',1)

def get_choice(options):
	while True:
		try:
			choice = raw_input('/'.join(options) + ': ').lower()
		except EOFError:
			return None
		if not choice: continue
		for o in options:
			if o.lower().startswith(choice):
				return o

def ask_if_previous_still_testing(master_doc, new_version):
	new_version_parsed = model.parse_version(new_version)
	xml = master_doc.toxml(encoding = 'utf-8')
	master = model.ZeroInstallFeed(qdom.parse(BytesIO(xml)))

	previous_versions = [impl.version for impl in master.implementations.values() if impl.version < new_version_parsed]
	if not previous_versions:
		return

	previous_version = max(previous_versions)

	# (all the <implementations> with this version number)
	previous_testing_impls = [impl for impl in master.implementations.values()
					if impl.version == previous_version
					and impl.upstream_stability == model.testing]

	if not previous_testing_impls:
		return

	print("The previous release, version {version}, is still marked as 'testing'. Set to stable?".format(
		version = model.format_version(previous_version)))
	if get_choice(['Yes', 'No']) != 'Yes':
		return

	ids_to_change = frozenset(impl.id for impl in previous_testing_impls)

	for impl in master_doc.getElementsByTagNameNS(XMLNS_IFACE, 'implementation'):
		if impl.getAttribute('id') in ids_to_change:
			impl.setAttribute('stability', 'stable')

def process(config, xml_file, delete_on_success):
	# Step 1 : check everything looks sensible, reject if not

	with open(xml_file, 'rb') as stream:
		xml_text = stream.read()
		sig_index = xml_text.rfind('\n<!-- Base64 Signature')
		if sig_index != -1:
			stream.seek(0)
			stream, sigs = gpg.check_stream(stream)
		else:
			sig_index = len(xml_text)
			sigs = []
		root = qdom.parse(BytesIO(xml_text))

	master = get_feed_url(root, xml_file)
	import_master = 'uri' in root.attrs

	if not import_master:
		root.attrs['uri'] = master	# (hack so we can parse it here without setting local_path)

	# Check signatures are valid
	if config.CONTRIBUTOR_GPG_KEYS is not None:
		for sig in sigs:
			if isinstance(sig, gpg.ValidSig) and sig.fingerprint in config.CONTRIBUTOR_GPG_KEYS:
				break
		else:
			raise SafeException("No trusted signatures on feed {path}; signatures were: {sigs}".format(
				path = xml_file,
				sigs = ', '.join([str(s) for s in sigs])))

	feed = model.ZeroInstallFeed(root)

	# Perform custom checks defined by the repository owner
	for impl in feed.implementations.values():
		problem = config.check_new_impl(impl)
		if problem:
			raise SafeException("{problem} in {xml_file}\n(this check was configured in {config}: check_new_impl())".format(
				problem = problem, xml_file = xml_file, config = config.__file__))

	feeds_rel_path = paths.get_feeds_rel_path(config, master)
	feed_path = join("feeds", feeds_rel_path)
	feed_dir = dirname(feed_path)
	if not os.path.isdir(feed_dir):
		os.makedirs(feed_dir)

	scm.ensure_no_uncommitted_changes(feed_path)

	if import_master:
		if os.path.exists(feed_path):
			with open(feed_path, 'rb') as stream:
				existing = stream.read()
			if existing == xml_text[:sig_index]:
				print("Already imported {feed}; skipping".format(feed = feed_path))
				if delete_on_success:
					os.unlink(xml_file)
				return None
			else:
				raise SafeException("Can't import '{url}'; non-identical feed {path} already exists.\n\n"
						    "To ADD new versions to this feed, remove the a 'uri' attribute from "
						    "the root element in {new}.\n\n"
						    "To EDIT the feed, just edit {path} directly rather than trying to add it again.\n\n"
						    "To RE-UPLOAD the archives, do that manually and then edit archives.db."
						    .format(url = feed.url, new = xml_file, path = feed_path))

	# Calculate commit message
	if import_master:
		name = basename(xml_file)
		if name == 'feed.xml':
			name = basename(dirname(xml_file))
		action = 'Imported {file}'.format(file = name)
	else:
		versions = set(i.get_version() for i in feed.implementations.values())
		action = 'Added {name} {versions}'.format(name = feed.get_name(), versions = ', '.join(versions))
	commit_msg = '%s\n\n%s' % (action, xml_text.decode('utf-8'))

	# Calculate new XML
	new_file = not os.path.exists(feed_path)
	git_path = relpath(feed_path, 'feeds')

	if import_master:
		assert new_file
		new_xml = xml_text[:sig_index]
	elif new_file:
		new_xml = create_from_local(master, xml_file)
	else:
		# Merge into existing feed
		try:
			new_doc = merge.merge_files(master, feed_path, xml_file)
		except merge.DuplicateIDException as ex:
			# Did we already import this XML? Compare with the last Git log entry.
			msg, previous_commit_xml = get_last_commit(git_path)
			if previous_commit_xml == xml_text:
				print("Already merged this into {feed}; skipping".format(feed = feed_path))
				return msg
			raise ex

		new_xml = None	# (will regenerate from new_doc below)

	# Step 2 : upload archives to hosting

	processed_archives = archives.process_archives(config, incoming_dir = dirname(xml_file), feed = feed)

	# Step 3 : merge XML into feeds directory

	# Prompt about existing testing versions
	if new_xml is None and getattr(config, 'TRACK_TESTING_IMPLS', True):
		new_versions = frozenset(impl.get_version() for impl in feed.implementations.values())
		if len(new_versions) == 1:
			ask_if_previous_still_testing(new_doc, list(new_versions)[0])
		new_xml = formatting.format_doc(new_doc)

	did_git_add = False

	try:
		with open(feed_path + '.new', 'wb') as stream:
			stream.write(new_xml)
		support.portable_rename(feed_path + '.new', feed_path)

		# Commit
		if new_file:
			subprocess.check_call(['git', 'add', git_path], cwd = 'feeds')
			did_git_add = True

		# (this must be last in the try block)
		scm.commit('feeds', [git_path], commit_msg, key = config.GPG_SIGNING_KEY)
	except Exception as ex:
		# Roll-back (we didn't commit to Git yet)
		print(ex)
		print("Error updating feed {feed}; rolling-back...".format(feed = xml_file))
		if new_file:
			if os.path.exists(feed_path):
				os.unlink(feed_path)
			if did_git_add:
				subprocess.check_call(['git', 'rm', '--', git_path], cwd = 'feeds')
		else:
			subprocess.check_call(['git', 'checkout', 'HEAD', '--', git_path], cwd = 'feeds')
		raise

	# Delete XML and archives from incoming directory
	if delete_on_success:
		os.unlink(xml_file)
		for archive in processed_archives:
			os.unlink(archive.incoming_path)

	return commit_msg.split('\n', 1)[0]

def process_incoming_dir(config):
	"""Current directory contains 'incoming'."""
	incoming_files = os.listdir('incoming')
	new_xml = []
	for i in incoming_files:
		if i.endswith('.xml'):
			new_xml.append(i)

	messages = []

	if new_xml:
		for xml in new_xml:
			print("Processing", xml)
			msg = process(config, os.path.join('incoming', xml), delete_on_success = True)
			if msg:
				messages.append(msg)
	else:
		pass #print('No .xml files in "incoming" directory (nothing to process)')
	
	return messages

def create_from_local(master_feed_url, new_impls_feed):
	with open(new_impls_feed, 'rb') as stream:
		doc = minidom.parse(stream)

	root = doc.documentElement
	root.setAttribute('uri', master_feed_url)

	to_remove = []
	for child in root.childNodes:
		if child.localName == 'feed-for' and child.namespaceURI == XMLNS_IFACE:
			# Remove <feed-for>
			to_remove.append(child)

			# Remove any preceeding commments too
			node = child
			while node.previousSibling:
				node = node.previousSibling
				if node.nodeType == Node.COMMENT_NODE or \
				   (node.nodeType == Node.TEXT_NODE and node.nodeValue.strip() == ''):
					to_remove.append(node)
				else:
					break

	for node in to_remove:
		root.removeChild(node)
	
	return formatting.format_doc(doc)
