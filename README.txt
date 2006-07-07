=======================================
Deliverance, high-speed themes for Zope
=======================================

Quick Start
-----------

1) Install lxml.

2) cd to the directory containing this README.

3) python ./deliverance.py

This runs the timeit function, showing average time to apply a simple theme.


Quick Server Start
------------------

1) python ./ThemedHTTPServer.py

2) Open http://localhost:8000/content/

3) Click on the links in the menu, especially the "Unthemed" link that shows a 
how content looks without a theme.


How Does This Work?
-------------------

There are proposals on zope.org and other places that explain the idea.  Here's 
the short version:

1) A configuration "map" points at a pile of HTML artifacts that look the 
way you'd like your site to look.  Let's call this a "theme".

2) A rule file defines boxes in that theme that should get filled by boxes 
coming from the dynamic side.

3) At startup, a one-time compilation processes turns the theme into a 
high-speed XSLT transform.
