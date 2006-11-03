========================================
meldX, an XML-inspired version of meld3
========================================

About
-----------

meldX is the four thousandth templating system, except it's an
un-system.  The goal is to impose a look-and-feel on content without
touching either look-and-feel or the content.

In a nutshell:

.. image:: zopesitethemesdiagram.png

Requirements
------------

meldX requires lxml.  It optionally requires uTidyLib if the theme
input isn't well-formed XML.

Quick Start
-----------

1. cd meldX

2. python ./runpipeline.py

3. Open var/finalresult.html in a browser.

What happened?  The following:

1. meldX retrieved the HTML content from http://www.plone.org/.

2. An XSLT was created with plug points as defined in the rule file.

3. This XSLT was then applied 20 times to a sample content doc.  The
   resulting HTML looks like plone.org, but has the info contained in
   ``contentdoc.xml``.  This document simulates what would come out of
   the CMS.


Less Quick Start
----------------

1. Edit rulefile.xml and change themeuri to point at some URL.

2. Edit the themexpath to pick boxes to shove stuff into.

3. python ./runpipeline.py

4. Look at the output of each pipeline stage in the var directory.

5. Open contentdoc.xml in a modern browser (IE, FF, Safari, new
   Opera).  The XSLT will be applied in-browser.


Background
----------

Chris McDonough has worked on meld3, a templating approach without
templates.  meldX is similar:

1) You don't put templating in the stuff the web designer sees.

2) You don't write "parsers", but instead, use off-the-shelf XML
   parsing tools.

meldX is different in the following ways:

1) Instead of sticking a meld:id attribute in the template, you use an
   XPath expression to point at an id, a class, a child relationship,
   whatever.

2) You don't write Python glue code.  Instead, a rule file governs the
   merging of content.

meldX tries to fulfill the ideas explained in the `Zope Site Themes
proposal <http://www.zope.org/Wikis/DevSite/Projects/ComponentArchitecture/SiteThemes>`_.
(The content at this link is also in ``contentdoc.html``, the sample
content in this directory.)
