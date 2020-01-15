

import os
import traceback
from repo import cmd

from http.server import SimpleHTTPRequestHandler
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request, urllib.error, urllib.parse
from socketserver import ThreadingMixIn

def handle(args):
	cmd.find_config()
	config = cmd.load_config()

	# Only serve files under these prefixes
	public_prefix = os.path.realpath('public') + os.path.sep
	archives_prefix = os.path.realpath('archives') + os.path.sep
	DOCUMENT_ROOTS = [ public_prefix, archives_prefix ]

	os.chdir(public_prefix)

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
					if not any (full_path.startswith(prefix) for prefix in DOCUMENT_ROOTS):
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
					stream = urllib.request.urlopen(self.path)
					send(stream, list(stream.headers.items()))
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
