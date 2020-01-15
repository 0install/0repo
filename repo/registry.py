# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.



import json

from zeroinstall import SafeException
from zeroinstall.support import basedir

def lookup(uri, missing_ok = False):
	"""Search repositories.json for the repository which hosts 'uri'."""
	path = basedir.load_first_config('0install.net', '0repo', 'repositories.json')
	if path:
		with open(path, 'rb') as stream:
			db = json.load(stream)
	else:
		db = {}
	
	from_registry = None
	for key, value in list(db.items()):
		if uri.startswith(key):
			if from_registry:
				raise SafeException("Multiple matching repositories! {a} and {b}".format(
					a = from_registry, b = value))
			from_registry = value

	if not from_registry:
		if missing_ok:
			return None
		else:
			raise SafeException("No registered repository for {uri} (hint: use '0repo register')".format(uri = uri))

	return from_registry
