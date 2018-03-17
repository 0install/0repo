# Copyright (C) 2018, Bastian Eicher
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import join
from xml.dom import minidom, Node

from repo import cmd, registry, merge, incoming, formatting
from repo.cmd import update

def handle(args):
	if not cmd.find_config(missing_ok = True):
		from_registry = registry.lookup(args.uri)
		assert from_registry['type'] == 'local', 'Unsupported registry type in %s' % from_registry
		os.chdir(from_registry['path'])

	config = cmd.load_config()

	rel_uri = args.uri[len(config.REPOSITORY_BASE_URL):]
	feed_path = join('feeds', config.get_feeds_rel_path(rel_uri))
	with open(feed_path, 'rb') as stream:
		doc = minidom.parse(stream)

	messages = []
	for impl in merge.find_impls(doc.documentElement):
		impl_id = impl.getAttribute("id")
		impl_version = impl.getAttribute("version")
		impl_stability = impl.getAttribute("stability")
		if impl_id == args.id or impl_version == args.id:
			if args.stability and impl_stability != args.stability:
				messages.append('Implementation {id} (version {version}) stability set to {stability}'.format(
					id = impl_id, version = impl_version, stability = args.stability))
				impl.setAttribute("stability", args.stability)

	if len(messages) > 0:
		commit_msg = 'Modified {uri}\n\n{messages}'.format(uri = args.uri, messages = '\n'.join(messages))
		new_xml = formatting.format_doc(doc)
		incoming.write_to_git(feed_path, new_xml, commit_msg, config)
		update.do_update(config)
