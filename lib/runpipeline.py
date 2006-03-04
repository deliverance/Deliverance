
import copy, time, urllib, os
from lxml import etree

namespaces = {
    'html': 'http://www.w3.org/1999/xhtml',
    'xsl': 'http://www.w3.org/1999/XSL/Transform',
}


# ---------- Preparation ---------
# Make sure the var directory exists, where we will write 
# the results from each stage

if not os.path.exists("var"):
    os.mkdir("var")

# ---------- Stage 1 ----------
# Retrieve the theme content from the rulefile, polish it 
# into well-formed XML, and save.

ruledoc = etree.ElementTree(file="rulefile.xml")
themeroot = ruledoc.xpath("/rules/themeroot")[0]
themeuri = themeroot.get("href")
themecontent = urllib.urlopen(themeuri).read()

# If the input isn't well-formed XML, clean it up
try:
    themedoc = etree.ElementTree(etree.XML(themecontent))
except etree.XMLSyntaxError:
    print "Cleaning up theme content at", themeuri
    import tidy
    options = dict(output_xhtml=1,
		   numeric_entities=1,
		   add_xml_decl=1, 
		   indent=1, 
		   tidy_mark=0)
    themecontent = str(tidy.parseString(themecontent, **options))
    themedoc = etree.ElementTree(etree.XML(themecontent))

themedoc.write("var/1-validthemefile.xml")


# ----------  Stage 2 ----------
# Merge rule file and theme html into one XML document.
themeroot.append(copy.deepcopy(themedoc.getroot()))
ruledoc.write("var/2-mergedruletheme.xml")


# ----------  Stage 3 ----------
# Process the rules and 
# generate <xsl:apply-templates> in the theme html's plug points.

stage3doc = etree.ElementTree(file="var/2-mergedruletheme.xml")
htmlroot = stage3doc.xpath("/rules/themeroot/html:html", 
			   namespaces)[0]

for rule in stage3doc.xpath("/rules/rule"):

    # Grab the node in the theme this refers to
    ruletype = rule.get("type")
    themexpath = rule.get("themexpath")
    contentxpath = rule.get("contentxpath")
    try:
	themenode = htmlroot.xpath(themexpath, namespaces)[0]
    except IndexError:
	print "No match for", themexpath
	continue

    # Depending on the rule type, create an xsl node
    if ruletype == "simplereplace":
	# This is a simple textnode replace
	print "Simple replace:", contentxpath, "will fill", themexpath
	del(themenode[:])
	themenode.text = None
	xslvalueof = etree.SubElement(themenode,
				      "{%s}value-of" % namespaces["xsl"])
	xslvalueof.set("select", contentxpath)

    elif ruletype == "simplecopy":
	# In this case, a subtree is copied over
	print "Simple copy:", contentxpath, "will fill", themexpath
	del(themenode[:])
	themenode.text = None
	xslvalueof = etree.SubElement(themenode,
				      "{%s}copy-of" % namespaces["xsl"])
	xslvalueof.set("select", contentxpath)

# Write the htmlroot to disk
etree.ElementTree(htmlroot).write("var/3-appliedrules.xml")


# ----------  Stage 4 ----------
# Apply the themecompiler.xsl stylesheet to generate 
# final stylesheet/theme document.

stage4doc = etree.ElementTree(file="var/3-appliedrules.xml")
themecompilerdoc = etree.ElementTree(file="themecompiler.xsl")

# Merge the applied rules into the themecompilerdoc
htmlroot = copy.deepcopy(stage4doc.getroot())
target = themecompilerdoc.xpath("id('target')")[0]
target.append(htmlroot)

themecompilerdoc.write("var/compiledtheme.xsl")


# ----------  Runtime Stage ----------
# Everything before this is done once, on startup.  This next 
# part is done per request

contentdoc = etree.ElementTree(file="contentdoc.xml")
processor = etree.XSLT(themecompilerdoc)

def main():
    # ---   Apply this theme to some content and time it ---
    start = time.time()
    iterations = 100
    for i in range(iterations):
	resultdoc = processor.apply(contentdoc)
	resultstring = processor.tostring(resultdoc).encode("utf-8")
	elapsed = (time.time() - start)/iterations

    outputfile = open("var/finalresult.html", "w")
    outputfile.write(resultstring)
    outputfile.close()
    msgfmt = "Applying theme %s times took an average of %s seconds"
    print msgfmt % (iterations, elapsed)

if __name__ == "__main__": main()
