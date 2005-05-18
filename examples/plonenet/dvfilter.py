
"""
mod_python theme filter for the Deliverance system.

This module gets registered as an Apache filter on outgoing content.
Most of the work is done in the themelib class.
"""

from mod_python import apache

from lib.plonenetlib import ThemeFilter
tf = ThemeFilter()

def outputfilter(filter):
	"""Function actually called by modpython for applying the theme"""

	filter.req.content_type = "text/html"

	xmlstring = filter.read()
	if xmlstring:
		response = tf.applyTheme(xmlstring)

		filter.write(response)
		filter.close()



