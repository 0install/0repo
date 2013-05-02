# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import join

from repo import incoming, build, catalog, cmd

def handle(args):
	cmd.find_config()
	config = cmd.load_config()
	messages = incoming.process_incoming_dir(config)
	do_update(config, messages)

def do_update(config, messages = None):
	feeds, files = build.build_public_feeds(config)

	files += [f.public_rel_path for f in feeds]

	files += catalog.write_catalog(config, feeds)

	os.chdir('public')

	# Add default styles, if missing
	resources_dir = join('resources')
	if not os.path.isdir(resources_dir):
		os.mkdir(resources_dir)
	for resource in ['catalog.xsl', 'catalog.css', 'feed.xsl', 'feed.css']:
		target = join('resources', resource)
		files.append(target)
		if not os.path.exists(target):
			with open(join(config.default_resources, resource), 'rt') as stream:
				data = stream.read()
			data = data.replace('@REPOSITORY_BASE_URL@', config.REPOSITORY_BASE_URL)
			with open(target, 'wt') as stream:
				stream.write(data)

	if not messages:
		messages.append('0repo update')
	config.upload_public_dir(files, message = ', '.join(messages))
