#!/usr/bin/env python
import unittest, os, sys, tempfile, shutil, atexit

my_dir = os.path.abspath(os.path.dirname(sys.argv[0]))

try:
	import coverage
except ImportError:
	cov = None
	print "Coverage module not found. Skipping coverage report."
else:
	cov = coverage.coverage(source = ['repo'])
	cov.start()

sys.argv.append('-v')

suite_names = [f[:-3] for f in os.listdir(my_dir)
		if f.startswith('test') and f.endswith('.py')]
suite_names.sort()

alltests = unittest.TestSuite()

for name in suite_names:
	m = __import__(name, globals(), locals(), [])
	test = unittest.defaultTestLoader.loadTestsFromModule(m)
	alltests.addTest(test)

a = unittest.TextTestRunner(verbosity=2).run(alltests)

print "\nResult", a
if not a.wasSuccessful():
	sys.exit(1)

if cov:
	cov.stop()
	#cov.html_report(directory = 'covhtml')
cov.report()
