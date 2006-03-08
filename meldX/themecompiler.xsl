<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns="http://www.w3.org/1999/xhtml"
    xmlns:html="http://www.w3.org/1999/xhtml"
    exclude-result-prefixes="html" version="1.0">
    <!-- Theme compiler.  Applied to the rule file to generate 
        an XSLT that gets applied to content. -->
    <xsl:output indent="yes" method="html"/>
    <xsl:template xml:id="target" match="/">
        <!-- The 3-appliedrules.xml will be shoved in here -->
    </xsl:template>
    <xsl:template match="node()|@*">
        <xsl:copy>
            <xsl:apply-templates select="node()|@*"/>
        </xsl:copy>
    </xsl:template>
</xsl:stylesheet>
