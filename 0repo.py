# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.
import sys
from repo import cmd
from zeroinstall import SafeException

version = '0.3'

try:
	cmd.main(sys.argv)
except SafeException as ex:
	import logging
	if logging.getLogger().isEnabledFor(logging.INFO):
		raise

	print(ex)
	sys.exit(1)
