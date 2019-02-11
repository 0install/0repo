# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess
from os.path import join, dirname, abspath

from zeroinstall import SafeException

from repo import scm

topdir = dirname(dirname(dirname(abspath(__file__))))

def handle(args):
	if args.key == '-':
		key = None
	else:
		# Get the fingerprint from the key ID (and check we have the secret key)
		try:
			keys = subprocess.check_output(['gpg', '-q', '--fixed-list-mode', '--fingerprint', '--with-colons', '--list-secret-keys', args.key])
		except subprocess.CalledProcessError as ex:
			raise SafeException("GPG key '{key}' not found ({ex})".format(key = args.key, ex = ex))

		in_ssb = False
		fingerprint = None
		for line in keys.split('\n'):
			bits = line.split(':')
			if bits[0] == 'ssb': in_ssb = True
			elif bits[0] == 'sec': in_ssb = False
			elif bits[0] == 'fpr':
				if in_ssb and fingerprint is not None:
					pass	# Ignore sub-keys (unless we don't have a primary - can that happen?)
				elif fingerprint is None:
					fingerprint = bits[9]
				else:
					raise SafeException("Multiple GPG keys match '{key}':\n{output}".format(
						key = args.key, output = keys))

		if fingerprint is None:
			raise SafeException("GPG key not found '{key}'".format(key = args.key))
		key = '0x' + fingerprint

	# Create the directory structure
	os.mkdir(args.path)
	os.chdir(args.path)
	os.mkdir('incoming')
	os.mkdir('feeds')
	os.mkdir('public')

	# Write the configuration file, with the GPG key filled in
	with open(join(topdir, 'resources', '0repo-config.py.template'), 'rt') as stream:
		data = stream.read()
	data = data.replace('"{{GPGKEY}}"', '"' + key + '"' if key else "None")
	with open('0repo-config.py', 'wt') as stream:
		stream.write(data)

	# Initialise the Git repository
	subprocess.check_call(['git', 'init', '-q', 'feeds'])
	scm.commit('feeds', [], 'Created new repository', key, extra_options = ['--allow-empty'])
