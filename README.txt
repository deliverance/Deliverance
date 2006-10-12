
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






