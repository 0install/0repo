# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from io import BytesIO

from xml.dom import Node

def format_node(node, indent):
	"""Ensure that every element is indented by the string 'indent'."""

	doc = node.ownerDocument

	elems = []

	for child in node.childNodes:
		if child.nodeType == Node.TEXT_NODE:
			data = child.data
			if data.count('\n') < 2:
				child.data = child.data.strip()
			elif not data.strip():
				# Preserve blank lines between elements
				child.data = '\n' * (data.count('\n') - 1)

		elif child.nodeType == Node.ELEMENT_NODE:
			elems.append(child)
	
	for elem in elems:
		node.insertBefore(doc.createTextNode(indent + '  '), elem)
		format_node(elem, indent + '  ')
	
	if elems:
		node.appendChild(doc.createTextNode(indent))

def format_doc(doc):
	"""Note: modifies 'doc'."""
	format_node(doc.documentElement, "\n")

	b = BytesIO()
	b.write(b'<?xml version="1.0" ?>\n')
	b.write(doc.documentElement.toxml(encoding = 'utf-8'))
	b.write(b'\n')
	return b.getvalue()
