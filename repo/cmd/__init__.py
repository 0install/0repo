# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import argparse
import os
import sys
import logging
from os.path import join, dirname, abspath

import zeroinstall.injector.config
from zeroinstall import SafeException
from repo import archives

def main(argv):
	parser = argparse.ArgumentParser(description='Manage a 0install repository.')
	parser.add_argument('--verbose', '-v', help='more verbose output', action='count')
	subparsers = parser.add_subparsers(dest='subcommand')

	parser_import = subparsers.add_parser('add', help='import pre-existing feeds into 0repo')
	parser_import.add_argument('path', metavar='PATH', nargs='+',
			   help='the signed feeds to import')

	parser_create = subparsers.add_parser('create', help='create a new repository')
	parser_create.add_argument('path', metavar='DIR',
			   help='the directory to create to hold the new repository')
	parser_create.add_argument('key', metavar='GPGKEY',
			   help='the GPG key used to sign the generated feeds and commits')

	subparsers.add_parser('register', help='add this repository location to ~/.config/...')

	subparsers.add_parser('reindex', help='update archives.db from archives directory')

	subparsers.add_parser('update', help='process "incoming" and generate output files')

	parser_proxy = subparsers.add_parser('proxy', help='run a http proxy which serves all repository URLs directly from the "public" directory')
	parser_proxy.add_argument('-p', '--port', help='the port to run the HTTP proxy on', default=8080, type=int)


	if len(argv) == 1:
		argv = argv + ['update']

	args = parser.parse_args(argv[1:])

	if args.verbose == 1:
		logging.getLogger().setLevel(logging.INFO)
	elif args.verbose > 1:
		logging.getLogger().setLevel(logging.DEBUG)
	
	logging.info("Starting 0repo")

	cmd = __import__('repo.cmd.' + args.subcommand, globals(), locals(), [args.subcommand], 0)
	cmd.handle(args)

def find_config(missing_ok = False):
	"""Change to parent directory until we find one with 0repo-config.py."""

	# Walk up the directory tree to find the root of the repository
	while not os.path.isfile('0repo-config.py'):
		if os.path.samefile('.', '..'):
			if missing_ok:
				return False
			raise SafeException('0repo must be run from a repository directory (a directory that contains\n'
					    'a "0repo-config.py" file). To create a new repository, use "0repo create"')
		os.chdir('..')
	return True

def load_config():
	"""Load 0repo-config.py from the current directory."""
	import importlib
	sys.path.insert(0, abspath('.'))
	config = importlib.import_module('0repo-config')
	del sys.path[0]

	config.default_resources = join(dirname(dirname(dirname(abspath(__file__)))), 'resources')
	for setting in ['REPOSITORY_BASE_URL', 'ARCHIVES_BASE_URL', 'LOCAL_ARCHIVES_BACKUP_DIR']:
		value = getattr(config, setting)
		if not value.endswith('/'):
			setattr(config, setting, value + '/')

	config.archive_db = archives.ArchiveDB("archives.db")

	config.zconfig = zeroinstall.injector.config.load_config()

	return config
