===============
Random Notes
===============

This file collects random points to weave into other document docs.

0) You can do runtime creation of themes from remote URLs.  This is a lot easier than 
you'd think.  It could be possible to even build a reasonably smart, productive web 
front end for finding the plug points on each side.  (About the only part that would 
take some thinking is URL rewriting for stuff that keeps getting served by another 
host, such as images and CSS.)

1) The mod_python integration is done as a handler rather than a filter.  This is just 
historical: In something else, am currently using the module to also resolve certain 
URLs that are managed in an XML "map".

2) For the XML "map" stuff, xml:id support is what makes it so fast.  However, this 
imposes some limitations.  For example, you can't have slashes in xml:id values.

3) Yeh, it doesn't have tests, other than the timeit function at the bottom 
of deliverance.py.  I'm not yet much of a programmer.  I hope to fix this deficiency 
during downtime in July.

4) Neat point: Because of XInclude, the appmap XML document has everything it 
needs, including the generated stuff, in a view-source friendly format.   Want to 
see what's happening?  Just dump the XML document and look at it.

5) The theme doesn't have to be well-formed XML.  The HTMLParser can handle garbage as 
input and generate well-formed (though perhaps not valid) stuff on output.

6) The append rule in etc/themerules.xml shows that you can easily copy page-specific 
CSS, JS, etc. from the content document's <head> into the resulting <head>.

7) Extensibility is provided through XML namespaces and lxml's namespace binding 
support.  Want a new rule?  Just add it and bind a Python handler to it.

8) The "compilation" step provides a nice opportunity to accomplish two goals:

a. Make things simple.  Deliverance doesn't expose XSLT to users.  Other things 
can be hidden as well.

b. Optimize.  If there are calculations that are dynamic, but only calculated 
once, they can be moved into this little pipeline.
