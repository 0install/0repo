# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from __future__ import print_function

import os
from os.path import join
from xml.dom.minidom import getDOMImplementation
from xml.dom import XMLNS_NAMESPACE

from zeroinstall.injector.namespaces import XMLNS_IFACE

from . import namespace

XMLNS_CATALOG = "http://0install.de/schema/injector/catalog"

catalog_header = '''<?xml version="1.0" encoding="utf-8"?>
<?xml-stylesheet type='text/xsl' href='resources/catalog.xsl'?>
'''

catalog_names = frozenset(["name", "summary", "description", "homepage", "icon", "category", "entry-point"])

def write_catalog(config, feeds):
	cat_ns = namespace.Namespace()
	cat_ns.register_namespace(XMLNS_CATALOG, "c")

	impl = getDOMImplementation()
	cat_doc = impl.createDocument(XMLNS_CATALOG, "c:catalog", None)
	cat_root = cat_doc.documentElement
	cat_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:c', XMLNS_CATALOG)
	cat_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns', XMLNS_IFACE)

	for feed in feeds:
		feed_root = feed.doc.documentElement

		elem = cat_doc.createElementNS(XMLNS_IFACE, "interface")
		elem.setAttribute('uri', feed_root.getAttribute("uri"))
		for feed_elem in feed_root.childNodes:
			if feed_elem.namespaceURI == XMLNS_IFACE and feed_elem.localName in catalog_names:
				elem.appendChild(cat_ns.import_node(cat_doc, feed_elem))
		cat_root.appendChild(elem)

	catalog_file = join('public', 'catalog.xml')
	with open(catalog_file + '.new', 'wt') as stream:
		stream.write(catalog_header)
		cat_doc.documentElement.writexml(stream)
	os.rename(catalog_file + '.new', catalog_file)
