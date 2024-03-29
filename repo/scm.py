# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.



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
	keys = subprocess.check_output(['gpg', '-q', '--fixed-list-mode', '--with-colons', '--list-secret-keys', keyid], encoding='utf-8')
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

	gpg_override_applied = False
	if key:
		name, email = uid_from_fingerprint(key)
		env['GIT_COMMITTER_NAME'] = name
		env['GIT_COMMITTER_EMAIL'] = email
		env['GIT_AUTHOR_NAME'] = name
		env['GIT_AUTHOR_EMAIL'] = email

		# Force Git for Windows to use same version of GnuPG as 0repo
		if os.name == 'nt' and 'GNUPG_PATH' in env:
			subprocess.check_call(['git', 'config', 'gpg.program', env['GNUPG_PATH']], cwd = cwd)
			gpg_override_applied = True

	import tempfile
	msg_file = tempfile.NamedTemporaryFile(delete=False)
	try:
		msg_file.write(msg.encode('utf-8'))
		msg_file.close()
		subprocess.check_call(['git', 'commit', '-q', '-F', msg_file.name] + (['-S' + key] if key else []) + extra_options + ['--'] + paths,
				      cwd = cwd,
				      env = env)
	finally:
		if gpg_override_applied:
			subprocess.check_call(['git', 'config', '--unset', 'gpg.program'], cwd = cwd)
		msg_file.close()
		os.remove(msg_file.name)
