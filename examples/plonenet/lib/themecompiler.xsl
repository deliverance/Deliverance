<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
    xmlns:html="http://www.w3.org/1999/xhtml" xmlns="http://www.w3.org/1999/xhtml"
    xmlns:dv="http://www.zope.org/deliverance">
    <!-- The compiler for the  themes and boxes.  Pulls in static content from 
    the theme file, the config file, and the model. This XSLT is ultimately 
    applied to a particular document in the site.  For performance reasons, we 
    do as much work up front as possible. -->
    <xsl:output indent="yes"/>
    <xsl:strip-space elements="*"/>
    <xsl:template match="/">
        <xsl:apply-templates select="node()|@*"/>
    </xsl:template>
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:for-each select="@*">
                <xsl:copy/>
            </xsl:for-each>
            <xsl:choose>
                <xsl:when test="@id = /xsl:stylesheet/dv:themerules/dv:rule/@themeid">
                    <xsl:element name="xsl:copy-of">
                        <xsl:attribute name="select">
                             <xsl:value-of
                                select="/xsl:stylesheet/dv:themerules/dv:rule[@themeid=current()/@id]/@docxpath"
                            />
                        </xsl:attribute>
                    </xsl:element>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates select="node()"/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:copy>
    </xsl:template>
</xsl:stylesheet>
