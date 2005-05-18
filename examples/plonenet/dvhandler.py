
from mod_python import apache
from lib.sxcfile import SXCFile
from lib.plonenetlib import Pipeline
import os

root = os.path.split(os.path.abspath(__file__))[0]
sxcfilename = os.path.join(root, "content/pfdata.sxc")
sxc = SXCFile(sxcfilename)

# Test page for the "/echo123" request
echofile = open(os.path.join(root, "content/echo123.xml"), "r")
echoxml = echofile.read()
echofile.close()

def handler(req):

	# Now assign the PATH_INFO part
	pathinfo = req.path_info.split("/")

	viewname = pathinfo[1]
	if (len(pathinfo) == 3) and (pathinfo[2]):
		viewarg = pathinfo[2]
	else:
		viewarg = ''

	pipeline = Pipeline(sxc.content, os.path.join(root, "content/index.xsl"))
	response = pipeline.transformToString(viewname, viewarg)
	req.content_type = "text/xml"

	# First check to see if the request is for the test page
	if req.path_info == "/echo123":
		response = echoxml

	req.write(response)
	return apache.OK
