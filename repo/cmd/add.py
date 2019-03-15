# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import abspath

from zeroinstall.injector import qdom

from repo import incoming, cmd, registry
from repo.cmd import update

def handle(args):
	files = [abspath(f) for f in args.path]

	if not cmd.find_config(missing_ok = True):
		# Import into appropriate registry for this feed
		with open(files[0], 'rb') as stream:
			doc = qdom.parse(stream)
		master = incoming.get_feed_url(doc, files[0])

		from_registry = registry.lookup(master)

		assert from_registry['type'] == 'local', 'Unsupported registry type in %s' % from_registry
		os.chdir(from_registry['path'])

		print("Adding to registry '{path}'".format(path = from_registry['path']))

	config = cmd.load_config()

	messages = []
	for feed in files:
		print("Adding", feed)
		msg, _ = incoming.process(config, feed, delete_on_success = False)
		if msg:
			messages.append(msg)
	update.do_update(config, messages = messages)
