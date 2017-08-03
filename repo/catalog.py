# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import join
from xml.dom import minidom
from xml.dom import XMLNS_NAMESPACE

from zeroinstall.injector.namespaces import XMLNS_IFACE
from zeroinstall import support
from zeroinstall.support import xmltools

from . import namespace, build

XMLNS_CATALOG = "http://0install.de/schema/injector/catalog"

catalog_header = b'''<?xml version="1.0" encoding="utf-8"?>
<?xml-stylesheet type='text/xsl' href='resources/catalog.xsl'?>
'''

catalog_names = frozenset(["name", "summary", "description", "homepage", "icon", "category", "entry-point"])

def write_catalog(config, feeds):
	cat_ns = namespace.Namespace()
	cat_ns.register_namespace(XMLNS_CATALOG, "c")

	impl = minidom.getDOMImplementation()
	cat_doc = impl.createDocument(XMLNS_CATALOG, "c:catalog", None)
	cat_root = cat_doc.documentElement
	cat_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:c', XMLNS_CATALOG)
	cat_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns', XMLNS_IFACE)

	custom_tags = {}
	for (name, ns, tags) in getattr(config, 'ADDITIONAL_CATALOG_TAGS', []):
		cat_ns.register_namespace(ns, name)
		cat_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:' + name, ns)
		custom_tags[ns] = tags

	feed_roots = [feed.doc.documentElement for feed in feeds]

	def get_name(feed_root):
		return feed_root.getElementsByTagName('name')[0].firstChild.wholeText

	for feed_root in sorted(feed_roots, key=get_name):
		elem = cat_doc.createElementNS(XMLNS_IFACE, "interface")
		elem.setAttribute('uri', feed_root.getAttribute("uri"))
		for feed_elem in feed_root.childNodes:
			ns = feed_elem.namespaceURI
			if ((ns == XMLNS_IFACE and feed_elem.localName in catalog_names) or
				(ns in custom_tags and feed_elem.localName in custom_tags[ns])):
				elem.appendChild(cat_ns.import_node(cat_doc, feed_elem))
		cat_root.appendChild(elem)
	
	catalog_file = join('public', 'catalog.xml')

	need_update = True
	if os.path.exists(catalog_file):
		with open(catalog_file, 'rb') as stream:
			old_catalog = minidom.parse(stream)
		need_update = not xmltools.nodes_equal(old_catalog.documentElement, cat_doc.documentElement)

	if need_update:
		new_data = build.sign_xml(config, catalog_header + cat_doc.documentElement.toxml(encoding = 'utf-8') + '\n')
		with open(catalog_file + '.new', 'wb') as stream:
			stream.write(new_data)
		support.portable_rename(catalog_file + '.new', catalog_file)
		print("Updated catalog.xml")

	return ['catalog.xml']
