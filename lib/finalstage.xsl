<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output indent="yes"/>
    <xsl:template match="/">
        <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
                <title>
                    <xsl:value-of select="id('contenttitle')"/>
                </title>
            </head>
            <body>
                <h1>THEME: This part comes from the theme</h1>
                <p>The theme provides quit a few of the pixels on the screen as well as lots of
                    stuff in the background, such as JS/CSS in the the <code>HEAD</code> node.</p>
                <p>The next part is a bunch of stuff from the actual content document that this
                    theme is being applied to.</p>
                <h4>Author: <xsl:value-of select="id('contentauthor')"/></h4>
                <xsl:copy-of select="id('contentbody')/*"/>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>
