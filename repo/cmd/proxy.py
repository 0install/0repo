from __future__ import print_function

import os
import traceback
from repo import cmd

from SimpleHTTPServer import SimpleHTTPRequestHandler
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import urllib2
from SocketServer import ThreadingMixIn

def handle(args):
	cmd.find_config()
	config = cmd.load_config()

	os.chdir("public")

	# Only server files under this prefix
	public_prefix = os.path.realpath(os.getcwd()) + os.path.sep

	class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
		pass

	class Proxy(SimpleHTTPRequestHandler):
		def do_GET(self):
			try:
				def send(src, headers):
					self.send_response(200)
					for name, val in headers:
						self.send_header(name, val)
					self.end_headers()
					try:
						self.copyfile(src, self.wfile)
					finally:
						src.close()

				if self.path.startswith(config.REPOSITORY_BASE_URL):
					rel_path = self.path[len(config.REPOSITORY_BASE_URL):]
					full_path = os.path.realpath(os.path.abspath(rel_path))
					if not full_path.startswith(public_prefix):
						self.send_error(403, "Forbidden: %s" % rel_path)
						raise Exception("Attempt to fetch file outside of '%s': %s'" %
								(public_prefix, full_path))

					try:
						headers = [('Content-Length', os.stat(rel_path).st_size)]
						send(open(rel_path), headers)
					except OSError:
						traceback.print_exc()
						self.send_error(404, "GET Not Found: %s" % rel_path)
				else:
					stream = urllib2.urlopen(self.path)
					send(stream, stream.headers.items())
			except:
				traceback.print_exc()
				self.send_response(500)

	httpd = ThreadedHTTPServer(('127.0.0.1', args.port), Proxy)
	print("To use:\nenv http_proxy='http://localhost:%s/' 0install [...]" % (args.port,))
	try:
		httpd.serve_forever()
	except:
		httpd.socket.close()
		raise
