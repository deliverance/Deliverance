
Quick Start to run tests 
-------------------------

The easiest way to get started is to check out the buildout: 

svn co https://svn.openplans.org/svn/deliverance.buildout deliverance.buildout

If you follow the instructions there and install nose and it's dependencies, 
you should be able to run tests by running nosetests from 
this directory. 


Otherwise to install manually: 

get workingenv.py from
http://cheeseshop.python.org/pypi/workingenv.py

Create a working enviornment for deliverance and its dependencies:  

workingenv.py deliverance_env
source deliverance_env/bin/activate

install a recent cvs version of libxml2,libxstl and svn lxml. 
You are likely to encounter segfaults and other failures if recent versions are not used.

$ easy_install nose 
$ easy_install FormEncode
$ easy_install elementtree
$ easy_install paste 

checkout deliverance: 
$ svn co http://codespeak.net/svn/z3/deliverance/branches/packaged deliverance

$ cd deliverance
$ nosetests 


Simple Tests
------------

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


WSGI Tests 
----------

test_wsgi.py contains tests which take the theme and content from the 
web and local pages found under test-data. 


Hand Transform 
--------------

a hand test may also be performed using the handtransform.py script 
run python handtransform.py --help for instructions. The result of the 
transform is output to standard out. 

To avoid lengthy command lines, the script can accept a file which describes 
the theme and rules to apply using the -f flag eg: 

python handtransform.py -f test-data/nycsr/nycsr.theme ./test-data/nycsr/openplans.html

where nycsr.theme contains something like: 

<blend 
   theme="http://www.nycsr.org" 
   baseurl="http://www.nycsr.org" 
   rules="./test-data/nycsr/nycsr.xml" /> 

and the second argument points to the content 



