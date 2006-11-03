-----------------------------------
Deliverance README
-----------------------------------

See: http://www.openplans.org/projects/deliverance
for more information


Contents: 
* What is Deliverance? 
* Quick Start to build deliverance 
* Deliverance Proxy 
* WSGI Middleware 
* Command Line Transformations 
* Simple Tests
* WSGI Tests 
* Quick Example

----------------------------------
What is Deliverance? 
----------------------------------

Deliverance is a non-invasive mechanism for combining HTML content produced 
by other systems and normal web pages that typify a desired look and feel 
(themes) using a set of rules. This approach allows the "branding" aspects 
of a design to remain separate from content production, allows designers to 
avoid using and mixing in particular template syntaxes and allows reuse of 
existing static designs. 


-----------------------------------
Quick Start to build Deliverance
-----------------------------------

The easiest way to get Deliverance installed is to checkout the
buildout and follow the instructions found there.

$ svn co https://codespeak.net/svn/z3/deliverance/deliverance.buildout 


Otherwise, to install Deliverance manually, first get workingenv.py
from http://cheeseshop.python.org/pypi/workingenv.py. Create a working
environment for Deliverance and its dependencies:

$ workingenv.py deliverance_env 
$ source deliverance_env/bin/activate


Then install recent versions of libxml2, libxslt and lxml.  You are
likely to encounter segfaults and other failures if recent versions
are not used.

Checkout and setup Deliverance, then make sure your installation is
complete by running the tests:

$ svn co http://codespeak.net/svn/z3/deliverance/trunk/ deliverance
$ cd deliverance 
$ python setup.py develop  
$ nosetests


You can also run the tests like this:

$ deliverance_env/bin/deliverance-tests 
$ deliverance_env/bin/deliverance-speed 


----------------------------------------------
Deliverance Proxy
----------------------------------------------

The deliverance proxy is a standalone application which serves a
themed version of some web location using a theme and a set of rules.

eg:
$ deliverance-proxy --serve=localhost:5001 --proxy=localhost:8080 
		--theme=http://www.example.org 
		--rule=file:///some/path/somerulesfile.xml

This example provides a themed version of a local webserver at port
8080 served on port 5001. The theme page is http://www.example.org and
the rules are specified in somerulesfile.xml.

For more options, run:

$ deliverance-proxy --help 


------------------------------------------------
WSGI Middleware 
------------------------------------------------

Deliverance can also be used directly in a WSGI stack using the python
class in deliverance.wsgifilter.DeliveranceMiddleware.  See
deliverance/wsgifilter.py and deliverance/test_wsgi.py for examples.
 


-------------------------------------------------
Command Line Transformations 
-------------------------------------------------


The command line tool used to execute Deliverance is called
deliverance-handtransform.  For instructions, run:

$ deliverance-handtransform --help 

The theme, rules and other parameters are specified using command line
options -t, -r, etc.  The result of the transform is output to
standard out.

To avoid lengthy command lines, the tool can accept a "blend" file,
using the -f flag, which describes the theme and rules to apply.

eg:

$ deliverance-handtransform -f ./blendfile.xml http://www.example.org

The second argument refers to the content; blendfile.xml contains
something like:

<blend theme="http://www.example.org" 
   baseurl="http://www.example.org" 
   rules="./example-rules.xml" /> 



------------------------------------------------
Simple Tests
------------------------------------------------

There are a number of tests in the test-data directory that follow the form:

<?xml version="1.0" encoding="UTF-8"?>
<deliverance-test-suite>
<deliverance-test>
  <rules xmlns="http://www.plone.org/deliverance">
     ... rules as described at http://www.openplans.org/projects/deliverance/specification
  </rules>

  <theme base="http://example.com"> 
     ... theme html 
  </theme>

  <content> 
     ... content html 
  </content>
 
  <output>
     ... expected output of applying rules to theme and content 
  </output> 
</deliverance-test>

... 

</deliverance-test-suite>

----------------------------------------------
WSGI Tests 
----------------------------------------------

test_wsgi.py contains tests which take the theme and content from the 
web and local pages found under test-data. 


----------------------------------------------
Quick Example 
----------------------------------------------

Deliverance combines a content web page with a theme web page, containing no special markup, 
according to a set of rules. Example: 


This is an unstyled page produced by myBoringTodoList.com/deliverance_user/:  
this page is the content page: 

<html>
  <head>
    <title>my boring todo page</title>
  <head>
  <body>
    <div id="todo">
      <h1>Things To Do</h1>
      <ul>
        <li>Feed the cat</li>
        <li>Wash the dishes</li>
      </ul>
    </div> 
  </body>
</html> 



Here is another web page that typifies how we'd like to see the todo list 
at excitingHomePage.com/deliverance_user/. 
this page is the theme: 

<html>
  <head>
    <style type="text/css">
      div {background: #00ffdd;}
      li {list-style-type: disc;}
    </style>
    <title>my exciting home page</title>
  </head>
  <body>
     <h1>Deliverance User's Exciting Page</h1>
     <div id="wishes">
       I wish my todo list looked this cool
     </div>
  </body> 
</html>

Here are some deliverance rules that put the todo list into the 
exciting home page and take away the wish. This tells deliverance
to replace the "wishes" div in the exciting home page with the 
"todo" div in the content page. 

<?xml version="1.0" encoding="UTF-8"?>

<rules xmlns="http://www.plone.org/deliverance" >
  <replace theme="//div[@id='wishes']" content="//div[@id='todo']" />
</rules>

Here is the output: 

<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <style type="text/css">
      div {background: #00ffdd;}
      li {list-style-type: disc;}
    </style>
    <title>my exciting home page</title>
  </head>
  <body>
    <h1>Deliverance User's Exciting Page</h1>
    <div id="todo">
      <h1>Things To Do</h1>
      <ul>
        <li>Feed the cat</li>
        <li>Wash the dishes</li>
      <ul>
    </div>
  </body>
</html>

see http://www.openplans.org/projects/deliverance for more information. 
There are many other examples in deliverance/test-data 
