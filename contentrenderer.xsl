<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns="http://www.w3.org/1999/xhtml" xmlns:html="http://www.w3.org/1999/xhtml"
    xmlns:at="http://www.plone.org/archetypes" exclude-result-prefixes="at html" version="1.0">
    <xsl:output indent="yes"/>
    <xsl:param name="siteurl">/sandboxes/z3/deliverance/branches/mphandler/content</xsl:param>
    <xsl:param name="pathinfo">providers.zea</xsl:param>
    <xsl:variable name="contentnode" select="id($pathinfo)"/>
    <xsl:template match="/">
        <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
                <title>
                    <xsl:value-of select="$contentnode/@title"/>
                </title>
            </head>
            <body>
                <div id="navtree">
                    <xsl:apply-templates select="id('root')" mode="navtree"/>
                </div>
                <div id="pagecontent">
                    <xsl:apply-templates select="$contentnode"/>
                </div>

            </body>
        </html>
    </xsl:template>
    <xsl:template match="at:collection" mode="navtree">
        <div>
            <h2>sitenav</h2>
            <ul>
                <xsl:for-each select=".//*[@name]">
                    <li>
                        <a href="{$siteurl}/{@name}">
                            <xsl:value-of select="@title"/>
                        </a>
                    </li>
                </xsl:for-each>
            </ul>

        </div>
    </xsl:template>

    <xsl:template match="at:providers">
        <ul>
            <li>Item one</li>
            <xsl:for-each select="at:provider">
                <li>
                    <xsl:value-of select="@title"/>
                </li>
            </xsl:for-each>
        </ul>
    </xsl:template>

    <xsl:template match="at:provider">
        <p>Title:
            <xsl:value-of select="@title"/>
        </p>
    </xsl:template>

    <xsl:template match="at:localfile">
        <xsl:copy-of select="html:html/html:body/*"/>
    </xsl:template>

</xsl:stylesheet>
