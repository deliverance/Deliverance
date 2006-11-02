

See: http://www.openplans.org/projects/deliverance
for more information


Contents: 
* What's Deliverance? 
* Quick Start to build deliverance 
* Deliverance Proxy 
* WSGI Middleware 
* Command Line Transformations 
* Simple Tests
* WSGI Tests 
* Quick Example

----------------------------------
What's Deliverance? 
----------------------------------

Deliverance is a non-invasive mechanism for combining HTML content produced 
by other systems and normal web pages that typify a desired look and feel 
(themes) using a set of rules. This approach allows the "branding" aspects 
of a design to remain separate from content production, allows designers to 
avoid using and mixing in particular template syntaxes and allows reuse of 
existing static designs. 


-----------------------------------
Quick Start to build deliverance
-----------------------------------

The easiest way to get started is to checkout the buildout and follow the instructions
found there. 

svn co https://svn.openplans.org/svn/deliverance.buildout deliverance.buildout


Otherwise to install manually: 

get workingenv.py from
http://cheeseshop.python.org/pypi/workingenv.py

Create a working enviornment for deliverance and its dependencies:  

$ workingenv.py deliverance_env
$ source deliverance_env/bin/activate

install a recent cvs version of libxml2,libxstl and svn lxml. 
You are likely to encounter segfaults and other failures if recent versions are not used.

checkout deliverance: 
$ svn co http://codespeak.net/svn/z3/deliverance/branches/packaged deliverance

$ cd deliverance
$ python setup.py develop 
$ nosetests

you can also run: 
deliverance_env/bin/deliverance-tests 
deliverance_env/bin/deliverance-speed 

from the top level checkout directory

----------------------------------------------
Deliverance Proxy
----------------------------------------------

The deliverance proxy is a standalone application which serves a "themed" version of some web 
location given a theme page and a set of rules. 

eg:

deliverance-proxy --serve=localhost:5001 --proxy=localhost:8080 
                  --theme=http://www.example.org 
                  --rule=file:///some/path/somerulesfile.xml

provides a themed version of a local webserver at port 8080 served on port 5001. 
The theme page is http://www.example.org and somerulesfile.xml describes how to 
put the content from localhost:8080 together with the look of the webpage at 
http://www.example.org to produce the "themed" result. 

run deliverance-proxy --help for more options 

------------------------------------------------
WSGI Middleware 
------------------------------------------------

Deliverance theming can also used directly in a WSGI stack using 
deliverance.wsgifilter.DeliveranceMiddleware

see deliverance/wsgifilter.py and deliverance/test_wsgi.py for examples. 


-------------------------------------------------
Command Line Transformations 
-------------------------------------------------

a command line transformation may also be performed using the 
handtransform.py script. 

run python handtransform.py --help for instructions. The result of the 
transform is output to standard out. 

To avoid lengthy command lines, the script can accept a file which describes 
the theme and rules to apply using the -f flag eg: 

python handtransform.py -f ./example.theme http://www.example.org


The second argument refers to the content and example.theme contains something like: 

<blend 
   theme="http://www.example.org" 
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
