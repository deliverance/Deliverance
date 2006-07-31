======================
Changelog
======================

This document tracks major changes, as well as a TODO list.

TODO
----

1) I don't know why, but clicking Reload in the browser fails.  Basically, the filter seems to be given no data.


noapmapp
--------

This rewrite happened after Rob Miller started using the themes.  Below are notes written about the changes.

I decided to refactor everything, to make it simpler and more obvious, and to enable multiple themes.  Below are notes on the things I did on branches/noappmap:

1) etc/appmap.xml was changed to etc/thememap.xml

2) The rules are now inline in thememap.xml instead of an XInclude.

3) The structure of that XML is now changed:

  themes
      theme id="simple"
		layout (points to HTML file)
		rules
		generator (points to themecompiler.xsl)
		processordoc (the generated XSLT from the layout, rules, and generator)

4) Changed deliverance.py to thememap.py

5) Changed class AppMap to class ThemeMap.

6) Got rid of cruft:

  a. Removed remaining vestiges of my earlier in-memory content map.

  b. No longer use an lxml rule to make the processor.  It is now a method.

  c. Removed a bunch of unused files.

  d. Changed the "publish" method to be called "applyTheme".

  e. Removed the handler function in mpfilter.py

7) You can optional pass the filename of the thememap file to the ThemeMap constructor.

8) Parse each theme entry in the thememap.xml into a thememap.themes mapping.  This maps themeid to themeprocessor (the generated XSLT processor).

9) The themes were previously being generated using the same XSLT (themecompiler.xsl).  This is now a per-theme setting, allowing customization of the processing rules.  Later, we can also do some pipeline-ish stuff, such as embedding navigation menus in the generated theme.

10) Added an __str__ for ThemeMap.  This lets you see the XML for the whole enchilada:

  a. The original thememap.xml

  b. The HTML for the themes that came in via XInclude.

  c. The XSLT markup used for the theme compiler.

  d. The XSLT markup of the generated theme, to let you debug your XPaths.

11) Added multitheme support.  As mentioned above, there is a mapping (thememap.themes) of themeid to themeprocessors.  thememap.applyTheme now has an optional argument for the id of the theme.  If omitted, it will use the "default" theme, which currently is just the first listed.  You can add any of the following to the URL:

  ?theme=simple
  ?theme=spiral
  ?theme=default
  ?theme=notheme

12) mpfilter.py now looks for a "theme" attribute in the request to choose the theme.  If not supplied, it is assigned "spiral".

13) Some changes in the outputfilter, though ultimately I don't know if they made a substantive difference.  (I *did* remove the calculation of content length...was that needed?)

14) I found the problem with your substitutions.  It was my problem, actually...the xpath started with "//", which made it find the wrong theme, once we added two.  We should avoid the "//" XPath pattern, now that we have multiple themes in one thememap document.

The XPath is applied relative to the html:html node of the current theme.  Thus, I changed those rules to be html:body//html:h1 etc.

15) The spurious xml:base attribute that we got due to XInclude is now manually removed.

16) The files in the doc directory got a little bit of love.

