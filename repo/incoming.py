# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess
from io import BytesIO
from os.path import join, dirname, basename, relpath

from zeroinstall.injector import qdom, model, gpg, trust
from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall import SafeException

from repo import paths, archives

def ensure_no_uncommitted_changes(path):
	child = subprocess.Popen(["git", "diff", "--exit-code"], cwd = dirname(path), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
	stdout, unused = child.communicate()
	if child.returncode == 0:
		return

	raise SafeException('Uncommitted changes in {feed}!\n'
			    'In the feeds directory, use:\n\n'
			    '"git commit -a" to commit them, or\n'
			    '"git stash" to discard.\n\n'
			    'Changes are:\n{changes}'.format(feed = path, changes = stdout))

def process(config, xml_file, import_master = False):
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

	if import_master:
		master = root.attrs['uri']
	else:
		for child in root.childNodes:
			if child.name == 'feed-for' and child.uri == XMLNS_IFACE:
				# TODO: This actually gives us the interface. We currently assume we're adding to the
				# default feed for the interface, which is wrong. If there is a 'feed' attribute on the
				# <feed-for>, we should use that instead. This will also require updating 0publish.
				master = child.attrs['interface']
				break
		else:
			raise SafeException("Missing <feed-for> in " + basename(xml_file))

		root.attrs['uri'] = master	# (hack so we can parse it here without setting local_path)

	# Check signatures are valid
	if sigs or import_master:
		for sig in sigs:
			if sig.is_trusted(trust.domain_from_url(master)):
				break
		else:
			raise SafeException("No trusted signatures on feed {path}; signatures were {sigs}".format(
				path = xml_file,
				sigs = sigs))

	feed = model.ZeroInstallFeed(root)

	feeds_rel_path = paths.get_feeds_rel_path(config, master)
	feed_path = join("feeds", feeds_rel_path)
	feed_dir = dirname(feed_path)
	if not os.path.isdir(feed_dir):
		os.makedirs(feed_dir)

	if import_master:
		if os.path.exists(feed_path):
			raise SafeException("Can't import '{url}'; feed {path} already exists".format(
				url = feed.url,
				path = feed_path))
	else:
		ensure_no_uncommitted_changes(feed_path)

	# Step 2 : upload archives to hosting

	if import_master:
		processed_archives = []
	else:
		processed_archives = archives.process_archives(config, feed)

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
		action = 'Imported' if import_master else 'Merged'
		commit_msg = '%s %s\n\n%s' % (action, basename(xml_file), xml_text.encode('utf-8'))
		subprocess.check_call(['git', 'commit', '-q', '-m', commit_msg, '-S' + config.GPG_SIGNING_KEY, '--', git_path], cwd = 'feeds')
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
	if not import_master:
		os.unlink(xml_file)

	# Remove archives from incoming directory. Do this last, because it's
	# easy to re-upload the archives without causing problems, but we can't
	# reprocess once the archives have gone.
	archives.finish_archives(config, processed_archives)

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
			process(config, os.path.join('incoming', xml))
	else:
		print('No .xml files in "incoming" directory (nothing to process)')
