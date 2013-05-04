# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess
from os.path import dirname, abspath

from zeroinstall import SafeException

def ensure_no_uncommitted_changes(path):
	child = subprocess.Popen(["git", "diff", "--exit-code", "HEAD", "--", abspath(path)], cwd = dirname(path), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
	stdout, unused = child.communicate()
	if child.returncode == 0:
		return

	raise SafeException('Uncommitted changes in {feed}!\n'
			    'In the feeds directory, use:\n\n'
			    '"git commit -a" to commit them, or\n'
			    '"git stash" to discard.\n\n'
			    'Changes are:\n{changes}'.format(feed = path, changes = stdout))

def uid_from_fingerprint(keyid):
	keys = subprocess.check_output(['gpg', '-q', '--fixed-list-mode', '--with-colons', '--list-secret-keys', keyid])
	for line in keys.split('\n'):
		bits = line.split(':')
		if bits[0] == 'uid':
			if '<' not in bits[9]:
				raise SafeException("No email address in GPG identity: {id}".format(id = bits[9]))
			name, email = bits[9].split('<', 1)
			return name, '<' + email
	else:
		raise SafeException("GPG key not found: " + keys)

def commit(cwd, paths, msg, key, extra_options = []):
	env = os.environ.copy()
	name, email = uid_from_fingerprint(key)

	env['GIT_COMMITTER_NAME'] = name
	env['GIT_COMMITTER_EMAIL'] = email
	env['GIT_AUTHOR_NAME'] = name
	env['GIT_AUTHOR_EMAIL'] = email

	subprocess.check_call(['git', 'commit', '-q', '-m', msg, '-S' + key] + extra_options + ['--'] + paths,
			      cwd = cwd,
			      env = env)
