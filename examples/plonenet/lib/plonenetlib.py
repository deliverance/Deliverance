
from lxml import etree
from StringIO import StringIO
import os

moduledir = os.path.split(os.path.abspath(__file__))[0]
dvdir = os.path.abspath(os.path.join(moduledir, ".."))

class ThemeFilter:

	testdocfn = os.path.join(dvdir, "content/echo123.xml")
	
	def __init__(self):

		# The theme should already be "compiled" by running 
		# the compiltheme.sh script in this directory.  Later 
		# to be included here on startup when lxml supports XInclude.
		compiledthemefn= os.path.join(dvdir, 
									  "content/compiled-plonenettheme.xml")
		self.compiledthemedoc = etree.ElementTree(file=compiledthemefn)
		self.compiledstyle = etree.XSLT(self.compiledthemedoc)

		
	def applyTheme(self, xmlstring):
		"""Transform a string of XML into a themed response"""

		responsedocfile = StringIO(xmlstring)
		responsedoc = etree.parse(responsedocfile)

		response = self.compiledstyle.apply(responsedoc)

		return self.compiledstyle.tostring(response).encode("UTF-8")


class Pipeline:
	"""Given an XML content doc, grab a view and render a result"""

	def __init__ (self, contentdoc, stylefn):

		self.contentdoc = contentdoc
		self.stylefn = stylefn

	def transformToString(self, viewname, viewarg):
		
		# This is more painful than it should be.  You can't parameterize
		# the value for "mode" in XSLT, so we'll just hack it in here
		self.styledoc = etree.parse(self.stylefn)
		mode = self.styledoc.xpath("//*[@mode]")[0]
		mode.set("mode", viewname)
		variables = self.styledoc.xpath("/*/*[@name]")
		for variable in variables:
			if variable.get("name") == "viewname":
				variable.text = viewname
			if variable.get("name") == "viewarg":
				variable.text = viewarg

		self.style = etree.XSLT(self.styledoc)

		result = self.style.apply(self.contentdoc)
		return self.style.tostring(result).encode("UTF-8")
     

def themefilter_main():

	tf = ThemeFilter()
	xmlstring = open(tf.testdocfn).read()
	response = tf.applyTheme(xmlstring)

	print response

           
def contenthandler_main():

	f = open("../content/pfdata.xml")
	doc = etree.parse(f)
	pipeline = Pipeline(doc, "../content/index.xsl", "bycountry", "fr")

	response = pipeline.transformToString()
	print response
	#print etree.tostring(pipeline.contentdoc.getroot())

	return

if __name__ == "__main__":
	themefilter_main()
	#contentfilter_main()
