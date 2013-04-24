# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import join

from repo import incoming, build, catalog

def handle(config, args):
	incoming.process_incoming_dir(config)
	
	feeds = build.build_public_feeds(config)

	catalog.write_catalog(config, feeds)

	# Add default styles, if missing
	resources_dir = join('public', 'resources')
	if not os.path.isdir(resources_dir):
		os.mkdir(resources_dir)
	for resource in ['catalog.xsl', 'catalog.css', 'feed.xsl', 'feed.css']:
		target = join('public', 'resources', resource)
		if not os.path.exists(target):
			with open(join(config.default_resources, resource), 'rt') as stream:
				data = stream.read()
			data = data.replace('@REPOSITORY_BASE_URL@', config.REPOSITORY_BASE_URL)
			with open(target, 'wt') as stream:
				stream.write(data)
