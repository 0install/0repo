# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from zeroinstall.injector.namespaces import XMLNS_IFACE
from xml.dom import Node, XMLNS_NAMESPACE, XML_NAMESPACE

class Namespace(object):
	def __init__(self):
		self.namespace_prefixes = {}	# Namespace -> prefix

	def register_namespace(self, namespace, prefix = 'ns'):
		"""Return the prefix to use for a namespace.
		If none is registered, create a new one based on the suggested prefix.
		@param namespace: namespace to register / query
		@param prefix: suggested prefix
		@return: the actual prefix
		"""
		if namespace == XMLNS_IFACE:
			return None
		if namespace == XML_NAMESPACE:
			return "xml"
		existing_prefix = self.namespace_prefixes.get(namespace, None)
		if existing_prefix:
			return existing_prefix
		
		# Find a variation on 'prefix' that isn't used yet, if necessary
		orig_prefix = prefix
		n = 0
		while prefix in list(self.namespace_prefixes.values()):
			#print "Prefix %s already in %s, not %s" % (prefix, self.namespace_prefixes, namespace)
			n += 1
			prefix = orig_prefix + str(n)
		self.namespace_prefixes[namespace] = prefix

		return prefix

	def add_attribute_ns(self, element, uri, name, value):
		"""Set an attribute, giving it the correct prefix or namespace declarations needed."""
		if not uri:
			element.setAttributeNS(None, name, value)
		else:
			prefix = self.register_namespace(uri)
			element.setAttributeNS(uri, '%s:%s' % (prefix, name), value)
			if uri != XML_NAMESPACE:
				element.ownerDocument.documentElement.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:' + prefix, uri)

	def import_node(self, target_doc, source_node):
		"""Import a node for a new document, fixing up namespace prefixes as we go."""
		target_root = target_doc.documentElement

		new_node = target_doc.importNode(source_node, True)
		def fixup(elem):
			elem.prefix = self.register_namespace(elem.namespaceURI, elem.prefix)
			if elem.prefix:
				elem.tagName = elem.nodeName = '%s:%s' % (elem.prefix, elem.localName)
				target_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:' + elem.prefix, elem.namespaceURI)

			for (uri, name), value in list(elem.attributes.itemsNS()):
				if uri == XMLNS_NAMESPACE:
					elem.removeAttributeNS(uri, name)
				elif uri:
					new_prefix = self.register_namespace(uri)
					if uri != XML_NAMESPACE:
						target_root.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:' + new_prefix, uri)
					elem.removeAttributeNS(uri, name)
					elem.setAttributeNS(uri, '%s:%s' % (new_prefix, name), value)

			for child in elem.childNodes:
				if child.nodeType == Node.ELEMENT_NODE:
					fixup(child)

		fixup(new_node)
		return new_node
