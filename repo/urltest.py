# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.



import urllib.parse
import http.client as httplib
import ftplib

from zeroinstall import SafeException

def get_http_size(url, ttl = 3, method = None):
	address = urllib.parse.urlparse(url)

	if url.lower().startswith('http://'):
		http = httplib.HTTPConnection(address.hostname, address.port or 80)
	elif url.lower().startswith('https://'):
		http = httplib.HTTPSConnection(address.hostname, address.port or 443)
	else:
		assert False, url

	parts = url.split('/', 3)
	if len(parts) == 4:
		path = parts[3]
	else:
		path = ''

	if method is None:
		if address.hostname.endswith('.s3.amazonaws.com'):
			method = 'GET'	# HEAD doesn't work on S3 due to signature mismatch
		else:
			method = 'HEAD'

	http.request(method, '/' + path, headers = {'Host': address.hostname, 'User-agent': '0repo (http://0install.net/0repo.html)'})
	response = http.getresponse()
	try:
		if response.status == 200:
			l = response.getheader('Content-Length')
			if l is None:
				if method == "HEAD":
					print("No Content-Length header returned; requesting whole archive...")
					return get_http_size(url, ttl, method = "GET")
				else:
					return len(response.read())
			else:
				return int(l)
		elif response.status in (301, 302, 303):
			new_url_rel = response.getheader('Location') or response.getheader('URI')
			new_url = urllib.parse.urljoin(url, new_url_rel)
		else:
			raise SafeException("HTTP error: got status code %s for %s" % (response.status, url))
	finally:
		response.close()

	if ttl:
		print("Moved")
		print("Checking new URL {}...".format(new_url), end = '')
		assert new_url
		return get_http_size(new_url, ttl - 1)
	else:
		raise SafeException('Too many redirections.')

def get_ftp_size(url):
	address = urllib.parse.urlparse(url)
	ftp = ftplib.FTP(address.hostname)
	try:
		ftp.login()
		ftp.voidcmd('TYPE I')
		return ftp.size(url.split('/', 3)[3])
	finally:
		ftp.close()

def get_size(url):
	print("Checking {url}... ".format(url = url), end = '')
	try:
		scheme = urllib.parse.urlparse(url)[0].lower()
		if scheme.startswith('http') or scheme.startswith('https'):
			size = get_http_size(url)
		elif scheme.startswith('ftp'):
			size = get_ftp_size(url)
		else:
			raise SafeException("Unknown scheme '%s' in '%s'" % (scheme, url))
	except:
		print("ERROR")
		raise
	print(size, "bytes")
	return size
