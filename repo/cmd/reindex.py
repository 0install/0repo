# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
import subprocess
import shutil
from os.path import join, abspath, relpath

from repo import archives, cmd
from repo.cmd import update

from zeroinstall import SafeException

def handle(args):
	cmd.find_config()
	config = cmd.load_config()

	assert config.LOCAL_ARCHIVES_BACKUP_DIR, "No LOCAL_ARCHIVES_BACKUP_DIR!"

	db  = config.archive_db
	old_dir = os.getcwd()
	os.chdir(config.LOCAL_ARCHIVES_BACKUP_DIR)

	missing = set(db.entries.keys())
	seen = set()

	changes = 0
	need_backup = False

	for root, dirs, files in os.walk('.'):
		for f in files:
			if f.startswith('.'): continue

			rel_path = relpath(join(root, f), '.')

			sha1 = archives.get_sha1(rel_path)
			new = archives.StoredArchive(url = config.ARCHIVES_BASE_URL + rel_path, sha1 = sha1)

			existing = db.entries.get(f, None)

			if f in seen:
				raise SafeException("{}: DUPLICATE basename - not allowed!\nFirst:{}\nSecord:{}".format(f, existing, new))
			seen.add(f)

			if existing:
				missing.remove(f)

				if existing != new:
					need_backup = True
					changes += 1

					print("{}:".format(rel_path))
					if existing.sha1 != new.sha1:
						print("  Old SHA1: {old}\n  New SHA1: {new}".format(file = rel_path, old = existing.sha1, new = new.sha1))
					if existing.url != new.url:
						print("  Old URL: {old}\n  New URL: {new}".format(file = rel_path, old = existing.url, new = new.url))
			else:
				changes += 1
				print("{}: added to database: {url}".format(rel_path, url = new.url))

			db.entries[f] = new
	
	if missing:
		print("These archives were missing (but were not removed from the database)")
		for m in sorted(missing):
			print("  " + m)
	
	os.chdir(old_dir)
	
	if need_backup:
		backup_path = db.path + '.old'
		print("Old database saved as {}".format(backup_path))
		shutil.copyfile(db.path, backup_path)
	
	if changes:
		db.save_all()
		print("Updated {} (changes: {})".format(db.path, changes))

		if need_backup:
			print("Run '0repo update' to update public feeds.")
	else:
		print("No changes found")
