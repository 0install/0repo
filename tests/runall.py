#!/usr/bin/env python
import unittest, os, sys

my_dir = os.path.abspath(os.path.dirname(sys.argv[0]))

try:
	import coverage
except ImportError:
	cov = None
	print "Coverage module not found. Skipping coverage report."
else:
	if len(sys.argv) > 1:
		cov = None
	else:
		cov = coverage.coverage(source = ['repo'])
		cov.start()

testLoader = unittest.TestLoader()

if len(sys.argv) > 1:
	alltests = testLoader.loadTestsFromNames(sys.argv[1:])
else:
	alltests = unittest.TestSuite()

	suite_names = [f[:-3] for f in os.listdir(my_dir)
			if f.startswith('test') and f.endswith('.py')]
	suite_names.sort()

	for name in suite_names:
		m = __import__(name, globals(), locals(), [])
		t = testLoader.loadTestsFromModule(m)
		alltests.addTest(t)

a = unittest.TextTestRunner(verbosity=2).run(alltests)

print "\nResult", a
if not a.wasSuccessful():
	sys.exit(1)

if cov:
	cov.stop()
	cov.report()
