# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

from repo import incoming
from repo.cmd import update

def handle(config, args):
	for feed in args.path:
		print("import", feed)
		incoming.process(config, feed, import_master = True)
	update.do_update(config)
