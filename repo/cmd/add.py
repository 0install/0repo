# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import abspath
import json

from zeroinstall.support import basedir
from zeroinstall.injector import qdom

from repo import incoming, cmd
from repo.cmd import update

def handle(args):
	files = [abspath(f) for f in args.path]

	if not cmd.find_config(missing_ok = True):
		# Import into appropriate registry for this feed
		with open(files[0], 'rb') as stream:
			doc = qdom.parse(stream)
		master = incoming.get_feed_url(doc, files[0])

		path = basedir.load_first_config('0install.net', '0repo', 'repositories.json')
		if path:
			with open(path, 'rb') as stream:
				db = json.load(stream)
		else:
			db = {}
		
		from_registry = None
		for key, value in db.items():
			if master.startswith(key):
				if from_registry:
					raise SafeException("Multiple matching repositories! {a} and {b}".format(
						a = from_registry, b = value))
				from_registry = value

		if not from_registry:
			raise SafeException("No registered repository for {uri} (hint: use '0repo register')".format(uri = master))

		assert from_registry['type'] == 'local', 'Unsupported registry type in %s' % from_registry
		os.chdir(from_registry['path'])

		print("Adding to registry '{path}'".format(path = from_registry['path']))

	config = cmd.load_config()

	for feed in files:
		print("Adding", feed)
		incoming.process(config, feed, delete_on_success = False)
	update.do_update(config)
