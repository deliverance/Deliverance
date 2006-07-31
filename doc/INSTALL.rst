======================
Setting up Deliverance
======================

The whole idea of Deliverance is that it *shouldn't* be a system.
It's just a thin approach that leverages some serious work being done
by others.  In this case, Deliverance gets most of its value from:

  o Apache.  Don't fight it, love it!  Yeh, baby!

  o mod_python for both handlers and filters.

  o lxml and thus libxml2/libxslt.  This is 90% of the value
  proposition.

mod_python
----------

1) Grab mod_python.

2) Make sure you can do this:

  http://www.modpython.org/live/current/doc-html/inst-testing.html


lxml
-----

1) Get 1.0 or later of lxml:

  http://codespeak.net/lxml

2) Make sure you can run some of the tests.

3) Make sure you install it using the same Python used in mod_python.
   To confirm, put:

  from lxml import etree

...in the mptest.py module used above in the mod_python testing example.


Deliverance
-----------

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
