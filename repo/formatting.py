# Copyright (C) 2013, Thomas Leonard
# See the README file for details, or visit http://0install.net.

import os

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

def write_doc(doc, path):
	format_node(doc.documentElement, "\n")

	with open(path + '.new', 'wb') as stream:
		stream.write(b'<?xml version="1.0" ?>\n')
		doc.documentElement.writexml(stream)
		stream.write(b'\n')
	os.rename(path + '.new', path)
