# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, shutil
from os.path import join

from repo import incoming, build

catalog_header = '''<?xml version="1.0" encoding="utf-8"?>
<?xml-stylesheet type='text/xsl' href='catalog.xsl'?>
<catalog xmlns="http://0install.de/schema/injector/catalog">
'''

def handle(config, args):
	# Step 1. Process any new files in the incoming directory
	incoming.process_incoming_dir(config)
	
	# Step 2. Regenerate the signed feeds
	build.build_public_feeds(config)

	# Step 3. Generate catalog
	catalog_stylesheet = join('public', 'catalog.xsl')
	if not os.path.exists(catalog_stylesheet):
		shutil.copyfile(join(config.default_resources, 'catalog.xsl'), catalog_stylesheet)

	catalog_css = join('public', 'catalog.css')
	if not os.path.exists(catalog_css):
		shutil.copyfile(join(config.default_resources, 'catalog.css'), catalog_css)

	catalog_file = join('public', 'catalog.xml')
	with open(catalog_file + '.new', 'wt') as stream:
		stream.write(catalog_header)
		stream.write('</catalog>')
	os.rename(catalog_file + '.new', catalog_file)
