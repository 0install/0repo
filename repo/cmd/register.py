# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import join
import json

from zeroinstall.support import basedir

def handle(config, args):
	path = join(basedir.save_config_path('0install.net', '0repo'), 'repositories.json')
	if os.path.exists(path):
		with open(path, 'rb') as stream:
			db = json.load(stream)
	else:
		db = {}
	
	existing = db.get(config.REPOSITORY_BASE_URL, None)

	entry = {'type': 'local', 'path': os.getcwd()}

	if existing and existing == entry:
		print("Already registered in {path} (no changes made):\n{base}: {json}".format(
			path = path,
			base = config.REPOSITORY_BASE_URL,
			json = json.dumps(entry)))
		return

	db[config.REPOSITORY_BASE_URL] = entry

	with open(path + '.new', 'wb') as stream:
		json.dump(db, stream)
	os.rename(path + '.new', path)
	
	if existing:
		print("Updated entry in {path} to:".format(path = path))
	else:
		print("Created new entry in {path}:".format(path = path))

	print("{base}: {json}".format(base = config.REPOSITORY_BASE_URL, json = json.dumps(entry)))
