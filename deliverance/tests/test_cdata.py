from deliverance.util.cdata import escape_cdata, unescape_cdata
from nose.tools import assert_true, assert_false, assert_equals
from lxml.html import fromstring, tostring

docs = [
    """<script>
      //<![CDATA[
      if( 1 > 0 && 2 < 3 ) {
        alert("Success!");
      };
      //]]>
    </script>""",

    """<script>
      //<![CDATA[
      if( 1 > 0 && 2 < 3 ) {
        alert("Success!");
      };
      //]]>
    </script><script>
      //<![CDATA[
      if( 1 > 0 && 2 < 3 ) {
        alert("A second success!");
      };
      //]]>
      </script>""",

    """<script>
      1 > 0 && 2 < 3;

      //<![CDATA[
      if( 1 > 0 && 2 < 3 ) {
        alert("Success!");
      };
      //]]>
    </script><script>
      //<![CDATA[
      if( 1 > 0 && 2 < 3 ) {
        alert("A second success!");
      };
      //]]>
      </script>""",
    ]

def test_symmetry():
    for doc in docs:
        assert_equals(unescape_cdata(escape_cdata(doc)),
                      doc)

def test_content_preserved():
    output = escape_cdata(docs[0])
    assert "Success!" in output
    assert "1 > 0 && 2 < 3" not in output
    assert "1 __GT__ 0 __AMP____AMP__ 2 __LT__ 3" in output

    output = escape_cdata(docs[1])
    assert "Success!" in output
    assert "A second success!" in output

def test_no_escape_outside_cdata():
    output = escape_cdata(docs[2])
    assert " > " in output
    assert " && " in output
    assert " < " in output

def test_lxml_output():
    output = escape_cdata(docs[0])
    output = tostring(fromstring(output), method="xml")
    assert "&gt;" not in output
    assert "&lt;" not in output
    assert "&amp;" not in output

    output = escape_cdata(docs[1])
    output = tostring(fromstring(output), method="xml")
    assert "&gt;" not in output
    assert "&lt;" not in output
    assert "&amp;" not in output

    output = escape_cdata(docs[2])
    output = tostring(fromstring(output), method="xml")
    assert output.count("&gt;") == 1
    assert output.count("&lt;") == 1
    assert output.count("&amp;") == 2

