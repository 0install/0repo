# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

from repo import incoming, build, catalog

def handle(config, args):
	incoming.process_incoming_dir(config)
	
	feeds = build.build_public_feeds(config)

	catalog.write_catalog(config, feeds)
