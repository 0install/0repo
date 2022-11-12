# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.



import time
import os
import subprocess
from os.path import join, abspath

from zeroinstall.injector import model, qdom

from repo import incoming, build, catalog, cmd

DAY = 60 * 60 * 24
TIME_TO_GRADUATE = 14 * DAY

def handle(args):
	cmd.find_config()
	config = cmd.load_config()
	messages = incoming.process_incoming_dir(config)
	do_update(config, messages)

def do_update(config, messages = None):
	feeds, files = build.build_public_feeds(config)

	files += [f.public_rel_path for f in feeds]

	files += catalog.write_catalogs(config, feeds)

	feeds_dir = abspath('feeds')

	os.chdir('public')

	# Add default styles, if missing
	resources_dir = join('resources')
	if not os.path.isdir(resources_dir):
		os.mkdir(resources_dir)
	for resource in ['catalog.xsl', 'catalog.xsl.de', 'catalog.css', 'list.min.js', 'feed.xsl', 'feed.xsl.de', 'feed.css']:
		target = join('resources', resource)
		files.append(target)
		if not os.path.exists(target):
			with open(join(config.default_resources, resource), 'rt') as stream:
				data = stream.read()
			data = data.replace('@REPOSITORY_BASE_URL@', config.REPOSITORY_BASE_URL)
			with open(target, 'wt') as stream:
				stream.write(data)

	if not messages:
		messages = ['0repo update']
	config.upload_public_dir(files, message = ', '.join(messages))

	out = subprocess.check_output(['git', 'status', '--porcelain'], cwd = feeds_dir, encoding = 'utf-8').strip('\n')
	if out:
		print("Note: you have uncommitted changes in {feeds}:".format(feeds = feeds_dir))
		print(out)
		print("Run 'git commit -a' from that directory to save your changes.")

	if getattr(config, 'TRACK_TESTING_IMPLS', True):
		graduation_check(feeds, feeds_dir)

def graduation_check(feeds, feeds_dir):
	# Warn about releases that are still 'testing' a while after release
	now = time.time()
	def age(impl):
		released = impl.metadata.get('released', None)
		if not released:
			return 0
		released_time = time.mktime(time.strptime(released, '%Y-%m-%d'))
		return now - released_time

	shown_header = False
	for feed in feeds:
		with open(feed.source_path, 'rb') as stream:
			zfeed = model.ZeroInstallFeed(qdom.parse(stream))
			if zfeed.implementations:
				# Find the latest version number (note that there may be several implementations with this version number)
				latest_version = max(impl.version for impl in list(zfeed.implementations.values()))
				testing_impls = [impl for impl in list(zfeed.implementations.values())
						 if impl.version == latest_version and
						    impl.upstream_stability == model.stability_levels['testing'] and
						    age(impl) > TIME_TO_GRADUATE]
				if testing_impls:
					if not shown_header:
						print("Releases which are still marked as 'testing' after {days} days:".format(
							days = TIME_TO_GRADUATE / DAY))
						shown_header = True
					print("- {name} v{version}, {age} days ({path})".format(
						age = int(age(testing_impls[0]) / DAY),
						name = zfeed.get_name(),
						path = os.path.relpath(feed.source_path, feeds_dir),
						version = model.format_version(latest_version)))
