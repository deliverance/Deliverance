=====================
Debugging Deliverance
=====================

Since it is based on mod_python and lxml, Deliverance gains from its reliance on two well-known quantities (Python and XML technologies).  Still, getting all the pieces together can be a bit of a chore.  This document provides tips on debugging.

1. Use the command-line first.

Before anything else, run the command-line script and look at the output::

  python ./thememap.py

This will run the `main` function and show the output (plus timing information).  If the HTML doesn't look like what you expect, you can fix it without Apache and mod_python being in the way.


2. Inspect the thememap.

An instance of the ThemeMap class, for example thememap, contains all the information about the themes in an lxml tree.  You can do the following::

  import thememap.
  thememap = thememap.main()
  print thememap

The string representation of the instance prints the XML tree (thememap.tree).  ThemeMap aggregates the output of each stage into this thememap tree.  Thus, printing it shows:

  a. Each theme.

  b. The HTML layout for each theme.

  c. The rules used for each theme.

  d. The XSLT "generator" used to create the final XSLT.

  e. The final XSLT.

Item (e) is the most useful, as discussed next.


3. View and edit XSLT.

The XSLT mentioned above can be cut-and-pasted into a file, for example `generatedtheme.xsl`.  You can then do a number of debugging steps on that file:

a. Run xmllint on the `generatedtheme.xsl` you just saved to ensure it is well-formed
XML.

b. Open it in a decent XML-aware editor and ensure the XSLT is "valid".

c. Make sure the generator put XSLT instructions in the places you expected, for example, in the <title>.

d. Look at the XSLT instructions inserted into the theme HTœML and see if the XPaths look correct.


4. Play with the XML and XSLT.

This step is the most useful and shows why this approach was taken for Deliverance.  Because standard XML technologies are used, you can use a number of tools:

a. Use xsltproc against some of the sample content::

  xsltproc generatedtheme.xsl content/index.html

...and look at the transformation output.

b. Use an XML editor like oXygen to open the XML file (content/index.html) and try debugging the transformation using the XSLT debugger.

c. You can also view the transformation in an XML-aware web browser (IE, FF, Safari, Opera).  First, copy content/index.html to content/index.xml (making an XML mime type instead of HTML mime type for the browser.)  Next, change the first lines to look like this::

  <?xml version="1.0" encoding="UTF-8"?>
  <?xml-stylesheet href="../tmp/generatedtheme.xsl" type="text/xsl"?>

When you open content/index.xml in a browser, you should see the transformed output.


5. Check the XPath statements in the rules.

If you are getting output without error messages, but something (or nothing) is getting substituted into the theme, the cause is usually a bad XPath.  The first step is to do (3) above and look at the generated XSLT.  Perhaps the XPath in the rule for selecting the theme node didn't work.  If an XSLT instruction was put in, perhaps the XPath for selecting content didn't work.

The `getThemeNode` method in ThemeMap has a commented-out line that reports each time a rule finds a theme node.  You can uncomment this and run the module again, watching each time a rule finds a place in the theme to generate XSLT instructions.

You can also debug this manually by using lxml::

  from lxml import etree
  from thememap import nsmap
  themedoc = etree.ElementTree(file="themes/simple/sampletheme.xml")
  themedoc.xpath("html:head/html:title", nsmap)
  contentdoc = etree.ElementTree(file="content/index.html")
  contentdoc.xpath("html:head/html:title", nsmap)

