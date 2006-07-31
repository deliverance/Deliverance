=======================================
Deliverance, high-speed themes for Zope
=======================================

Quick Start
-----------

1) Install lxml.

2) cd to the directory containing this README.

3) python ./thememap.py

This runs the timeit function, showing average time to apply a simple theme.


Quick mod_python Start
----------------------

1) Edit mpfilter.conf and point it to where you put the SVN checkout.

2) In your Apache httpd.conf file, add a line like this::

  Include /Users/me/sandboxes/deliverance/trunk/mpfilter.conf
  (or wherever is the location of the checkout)

3) Shut Apache down and restart.

4) Keep an eye on the Apache error log::

  tail -f logs/error_log

5) Open a URL like this (or however you have your HTML files pointed to on 
whichever port)::

  http://localhost:9000/sandboxes/deliverance/trunk/

6) If that works, click on the on the "content" directory or go to this URL::

  http://localhost:9000/sandboxes/deliverance/trunk/content/intro.html


Customization Quick Start
-------------------------

1) Edit ``themes/simple/sampletheme.xml`` and add the following snippet 
**inside** the ``<div id="pageframe">``::

  <div id="pageauthor">Theme section for author</div>

2) Edit ``content/index.html`` and add the following in the ``<head>``:

  <meta name="dc.creator" content="Your Name"/>

3) Edit ``etc/thememap.xml`` and add a rule like the following::

  <replace theme="//html:div[@id='pageauthor']" 
      content="/html:html/html:head/html:meta[@name='dc.creator']/@content"/>
  
4) Restart Apache and reload the page.


How Does This Work?
-------------------

The doc directory contains more information on the why and what for Deliverance.
Here's the short version:

1) A configuration "map" points at a pile of HTML artifacts that look the 
way you'd like your site to look.  Let's call this look-and-feel the "theme".

2) A rule file defines boxes in that theme that should get filled by boxes 
coming from the dynamic side.

3) At startup, a one-time compilation processes turns the theme into a 
high-speed XSLT processor.  You don't need to learn XSLT to use Deliverance!
