# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess
from io import BytesIO
from os.path import join, dirname, basename, relpath

from zeroinstall.injector import qdom, model, gpg
from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall import SafeException

from repo import paths, archives, scm

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

def process(config, xml_file, delete_on_success):
	# Step 1 : check everything looks sensible, reject if not

	with open(xml_file, 'rb') as stream:
		xml_text = stream.read()
		sig_index = xml_text.rfind('\n<!-- Base64 Signature')
		if sig_index != -1:
			stream.seek(0)
			stream, sigs = gpg.check_stream(stream)
		else:
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

	if import_master:
		if os.path.exists(feed_path):
			with open(feed_path, 'rb') as stream:
				existing = stream.read()
			if existing == xml_text[:sig_index]:
				print("Already imported {feed}; skipping".format(feed = feed_path))
				if delete_on_success:
					os.unlink(xml_file)
				return
			else:
				raise SafeException("Can't import '{url}'; non-identical feed {path} already exists".format(
					url = feed.url,
					path = feed_path))
	else:
		scm.ensure_no_uncommitted_changes(feed_path)

	# Step 2 : upload archives to hosting

	processed_archives = archives.process_archives(config, incoming_dir = dirname(xml_file), feed = feed)

	# Step 3 : merge XML into feeds directory

	new_file = not os.path.exists(feed_path)
	git_path = relpath(feed_path, 'feeds')
	did_git_add = False

	try:
		if import_master:
			assert new_file
			with open(feed_path + '.new', 'wb') as stream:
				stream.write(xml_text[:sig_index])
			os.rename(feed_path + '.new', feed_path)
		else:
			# Merge into feed
			subprocess.check_call([os.environ['ZEROPUBLISH'], "--add-from", xml_file, feed_path])

		# Commit
		if new_file:
			subprocess.check_call(['git', 'add', git_path], cwd = 'feeds')
			did_git_add = True

		# (this must be last in the try block)
		if import_master:
			action = 'Imported {file}'.format(file = basename(xml_file))
		else:
			versions = set(i.get_version() for i in feed.implementations.values())
			action = 'Added {name} {versions}'.format(name = feed.get_name(), versions = ', '.join(versions))
		commit_msg = '%s\n\n%s' % (action, xml_text.encode('utf-8'))
		scm.commit('feeds', [git_path], commit_msg, key = config.GPG_SIGNING_KEY)
	except Exception as ex:
		# Roll-back (we didn't commit to Git yet)
		print(ex)
		print("Error updating feed {feed}; rolling-back...".format(feed = xml_file))
		if new_file:
			os.unlink(feed_path)
			if did_git_add:
				subprocess.check_call(['git', 'rm', '--', git_path], cwd = 'feeds')
		else:
			subprocess.check_call(['git', 'checkout', 'HEAD', '--', git_path], cwd = 'feeds')
		raise

	# Delete XML from incoming directory
	if delete_on_success:
		os.unlink(xml_file)

	# Remove archives from incoming directory. Do this last, because it's
	# easy to re-upload the archives without causing problems, but we can't
	# reprocess once the archives have gone.
	archives.finish_archives(config, processed_archives, delete_on_success)

def process_incoming_dir(config):
	"""Current directory contains 'incoming'."""
	incoming_files = os.listdir('incoming')
	new_xml = []
	for i in incoming_files:
		if i.endswith('.xml'):
			new_xml.append(i)

	if new_xml:
		for xml in new_xml:
			print("Processing", xml)
			process(config, os.path.join('incoming', xml), delete_on_success = True)
	else:
		print('No .xml files in "incoming" directory (nothing to process)')
