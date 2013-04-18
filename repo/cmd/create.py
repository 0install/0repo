# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os, subprocess, shutil
from os.path import join, dirname, abspath

topdir = dirname(dirname(dirname(abspath(__file__))))

def handle(args):
	os.mkdir(args.path)
	os.chdir(args.path)
	os.mkdir('incoming')
	os.mkdir('feeds')
	os.mkdir('public')
	subprocess.check_call(['git', 'init', '-q', 'feeds'])
	subprocess.check_call(['git', 'commit', '-q', '--allow-empty', '-m', 'Create new repository'], cwd = 'feeds')
	shutil.copyfile(join(topdir, 'resources', '0repo-config.py.template'), '0repo-config.py')
