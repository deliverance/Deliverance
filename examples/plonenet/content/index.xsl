<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
    xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="http://openoffice.org/2000/meta"
    xmlns:office="http://openoffice.org/2000/office">
    <xsl:output method="xml" doctype-public="-//W3C//DTD XHTML 1.1//EN"
        doctype-system="http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd"/>
    <xsl:variable name="viewname">providers</xsl:variable>
    <xsl:variable name="viewarg">bycountry</xsl:variable>
    <xsl:template match="/">
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head>
                <title>
                    <xsl:value-of select="/workbook/office:meta/dc:title"/>
                </title>
            </head>
            <body>
                <div>
                    <span id="page-heading">
                        <xsl:value-of select="/workbook/office:meta/dc:title"/>
                    </span>
                </div>
                <div id="content-body">
                    <xsl:apply-templates select="workbook" mode="about"/>
                </div>
            </body>
        </html>
    </xsl:template>
    <xsl:template match="workbook" mode="index">
        <div id="news">
            <h2>News</h2>
            <ul>
                <xsl:for-each select="tables/table[@id='News']/data/row">
                    <li title="{cell[4]}">
                        <xsl:value-of select="cell[3]"/>
                    </li>
                </xsl:for-each>
            </ul>
        </div>
        <p>plone.net is some static information collects all the business information for Plone into a well-organized,
            professional resource for decision-makers.</p>
        <p>This Plone Foundation website ...</p>
    </xsl:template>
    <xsl:template match="workbook" mode="todo">
        <h2>To Do Items</h2>
        <xsl:for-each select="tables/table[@id='Todo']/data/row">
            <div><xsl:value-of select="cell[2]"/></div>
        </xsl:for-each>
    </xsl:template>
    <xsl:template match="workbook" mode="about">
        <h2>About plone.net</h2>
    </xsl:template>
    <xsl:template match="workbook" mode="providers">
        <xsl:choose>
            <xsl:when test="$viewarg='bycountry'">
                <h3>Providers sorted by country</h3>
                <div>(sort <a href="/plone.net/providers">by company name</a>)</div>
                <xsl:apply-templates select="tables/table[@id='Companies']/data/row" mode="provider">
                    <xsl:sort select="cell[5]"/>
                </xsl:apply-templates>
            </xsl:when>
            <xsl:otherwise>
                <h3>Providers sorted alphabetically</h3>
                <div>(sort <a href="/plone.net/providers/bycountry">by country</a>)</div>
                <xsl:apply-templates select="tables/table[@id='Companies']/data/row" mode="provider"
                />
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="row" mode="provider">
        <div class="provider">
            <xsl:if test="cell[8]">
                <!--<img src="{cell[8]}" alt="{cell[2]}"/>-->
            </xsl:if>
            <h4>
                <xsl:value-of select="cell[2]"/>
            </h4>
            <div>Country: <xsl:value-of select="cell[5]"/>
            </div>
            <div>
                <xsl:value-of select="cell[3]"/>
            </div>
        </div>
    </xsl:template>
    <xsl:template match="workbook" mode="casestudies">
        <h2>Case Studies</h2>
    </xsl:template>
    <xsl:template match="workbook" mode="links">
        <h2>Links</h2>
    </xsl:template>
    <xsl:template match="table">
        <table>
            <tr>
                <xsl:for-each select="columns/column">
                    <th>
                        <xsl:value-of select="."/>
                    </th>
                </xsl:for-each>
            </tr>
            <xsl:for-each select="data/row">
                <tr>
                    <xsl:for-each select="cell">
                        <td>
                            <xsl:if test=".">
                                <xsl:value-of select="."/>
                            </xsl:if>
                        </td>
                    </xsl:for-each>
                </tr>
            </xsl:for-each>
        </table>
    </xsl:template>
</xsl:stylesheet>
