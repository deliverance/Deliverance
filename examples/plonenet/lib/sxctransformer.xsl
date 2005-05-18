<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
    xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="http://openoffice.org/2000/meta"
    xmlns:office="http://openoffice.org/2000/office" xmlns:table="http://openoffice.org/2000/table"
    xmlns:text="http://openoffice.org/2000/text">
    <xsl:template match="/">
        <workbook>
            <xsl:copy-of select="/*/office:document-meta/office:meta"/>
            <!-- The qualifier skips empty worksheets -->
            <tables>
                <xsl:apply-templates
                    select="/office:document-content/office:body/table:table[table:table-row[2]]"/>
            </tables>
        </workbook>
    </xsl:template>
    <xsl:template match="table:table">
        <table id="{@table:name}">
            <columns>
                <xsl:apply-templates select="table:table-row[1]" mode="columns"/>
            </columns>
            <data>
                <xsl:apply-templates select="table:table-row[position() > 1]"/>
            </data>
        </table>
    </xsl:template>
    <xsl:template match="table:table-row[1]" mode="columns">
        <xsl:for-each select="table:table-cell/text:p">
            <column>
                <xsl:value-of select="."/>
            </column>
        </xsl:for-each>
    </xsl:template>
    <xsl:template match="table:table-row">
        <row id="{table:table-cell[1]/text:p}">
            <xsl:apply-templates select="table:table-cell" mode="datacells"/>
        </row>
    </xsl:template>
    <xsl:template match="table:table-cell" mode="datacells">
        <cell colname="{position()}">
            <xsl:value-of select="text:p"/>
        </cell>
        <xsl:if test="@table:number-columns-repeated">
            <xsl:call-template name="repeatcell">
                <xsl:with-param name="repeatvalue" select="@table:number-columns-repeated - 1"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>
    <xsl:template name="repeatcell">
        <xsl:param name="repeatvalue"/>
        <!-- This named template is called when a cell repeats. Its job is to do a little
            recursion, calling itself until it has repeated an appropriate number of times.
        -->
        <cell colname="{position()}">
            <xsl:value-of select="text:p"/>
        </cell>
        <xsl:if test="$repeatvalue > 1">
            <xsl:call-template name="repeatcell">
                <xsl:with-param name="repeatvalue" select="$repeatvalue - 1"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>
</xsl:stylesheet>
