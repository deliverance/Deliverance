
Quick Start to run tests 
-------------------------

get workingenv.py from
http://cheeseshop.python.org/pypi/workingenv.py

Create a working enviornment for deliverance and its dependencies:  

workingenv.py deliverance_env
source deliverance_env/bin/activate

Install lxml using the buildout 
(full instructions at http://faassen.n--tree.net/blog/view/weblog/2006/10/03/0,  
 alternatively, install a recent cvs version of libxml2,libxstl and svn lxml. 
 You are likely to encounter segfaults if recent versions are not used.)

$ svn co https://infrae.com/svn/buildout/lxml-recent/trunk lxml-recent
$ cd lxml-recent
$ python bootstrap/bootstrap.py
$ bin/buildout

put the lxml egg into your deliverance environment 

$ cp -r lxml-recent/develop-eggs/lxml-<whatever>.egg deliverance_env/lib/python_2.4/

add a line to deliverance_env/lib/easy-install.pth like:
./lxml-<whatever>.egg

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



