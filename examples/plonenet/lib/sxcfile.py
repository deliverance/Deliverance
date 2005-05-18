

"""
Utility classes for handling OpenOffice.org spreadsheet files.

These classes put a wrapper around .sxc files.  The purpose is to make
these an generic way to edit Archetypes content in bulk.  Each tab
corresponds to an AT Type.  Each column maps to a property.  Each row
maps to an instance of data.

Effort will be made to also do round-trip.  Meaning, you can download
a pile of data as a .sxc, edit it, then upload, thus giving
round-trip.  Effort will also be made to detect edit conflicts at the
field level.

This module uses lxml, Martin Faassen's Python wrapper for libxml2.
"""

from zipfile import ZipFile
from lxml import etree
from StringIO import StringIO
import os

moduledir = os.path.split(os.path.abspath(__file__))[0]


class SXCFile:
	"""lxml wrapper to work on OO.o spreadsheet files

	This class (should! XXX) extends the lxml etree class to give
	methods for opening the .sxc zip file and retrieving the
	content.xml.  The class needs to ensure that the content.xml is
	valid OO.o, then provide convenience methods for easy access to
	the rows.  """

	def __init__ (self, zipfilename):

		zipfile = open(zipfilename, "r")	
		zf = ZipFile(zipfile)
		contentf = StringIO(zf.read("content.xml"))
		metaf = StringIO(zf.read("meta.xml"))

		content = etree.parse(contentf)
		meta = etree.parse(metaf)
		content.getroot().append(meta.getroot())

		stylefile = open(os.path.join(moduledir, "sxctransformer.xsl"))
		styledoc = etree.parse(stylefile)
		self.style = etree.XSLT(styledoc)

		# Now process this through an XSLT to make it simpler to deal with
		self.content = self.style.apply(content)

		self.table = self.content.xpath('/atdb/table[1]')
		self.fields = []
		for field in self.content.xpath("/atdb/table[1]/columns/column"):
			self.fields.append(field.text)

		self.rows = []
		for row in self.content.xpath("/atdb/table[1]/data/row"):
			thisrow = {}
			colpos = 0
			for cell in row.xpath("cell"):
				colname = self.fields[colpos]
				if cell.text is None: thisrow[colname] = None
				else: thisrow[colname] = cell.text
				colpos = colpos + 1
			self.rows.append(thisrow)

		return

	def __str__ (self):
		return self.style.tostring(self.content)

                
def main():

	sxc = SXCFile("../content/pfdata.sxc")

	print sxc
	return

if __name__ == "__main__": main()
