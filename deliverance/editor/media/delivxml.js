/*
* customized for Deliverance
*/

editAreaLoader.load_syntax["delivxml"] = {
	'COMMENT_SINGLE' : {}
	,'COMMENT_MULTI' : {'<!--' : '-->'}
	,'QUOTEMARKS' : {1: "'", 2: '"'}
	,'KEYWORD_CASE_SENSITIVE' : true
	,'KEYWORDS' : {
                'values' : [
                        'ruleset', 
                        'server-settings', 'server', 'execute-pyref', 'display-local-files', 'edit-local-files',
                        'dev-allow', 'dev-deny', 'dev-htpasswd', 'dev-user', 'dev-expiration',
                        'proxy', 'dest', 'request', 'response',
                        'theme', 'rule', 'replace', 'append', 'prepend', 'drop'
                        ],
                'attributes' : [
                        'href', 'pyref', 'content', 'theme', 'if-content', 'notheme',
                        'manytheme', 'nocontent', 'manycontent', 'href', 'move', 
                        'suppress-standard', 'class',
                        'domain', 'path', 'header', 'rewrite-links', 'request-header',
                        'response-header', 'environ', 'editable']
	}
	,'OPERATORS' :[
	]
	,'DELIMITERS' :[
	]
	,'REGEXPS' : {
		'xml' : {
			'search' : '()(<\\?[^>]*?\\?>)()'
			,'class' : 'xml'
			,'modifiers' : 'g'
			,'execute' : 'before' // before or after
		}
		,'cdatas' : {
			'search' : '()(<!\\[CDATA\\[.*?\\]\\]>)()'
			,'class' : 'cdata'
			,'modifiers' : 'g'
			,'execute' : 'before' // before or after
		}
                /* These get in the way of the KEYWORDS based highlighting */
		/*,'tags' : {
			'search' : '(<)(/?[a-z][^ \r\n\t>]*)([^>]*>)'
			,'class' : 'tags'
			,'modifiers' : 'gi'
			,'execute' : 'before' // before or after
		}*/
		/*,'attributes' : {
			'search' : '( |\n|\r|\t)([^ \r\n\t=]+)(=)'
			,'class' : 'attributes'
			,'modifiers' : 'g'
			,'execute' : 'before' // before or after
		}*/
	}
	,'STYLES' : {
		'COMMENTS': 'color: #AAAAAA;'
		,'QUOTESMARKS': 'color: #6381F8;'
		,'KEYWORDS' : {
			'values' : 'color: #0000FF;'
			,'attributes' : 'color: #009900;'
			}
		,'OPERATORS' : 'color: #E775F0;'
		,'DELIMITERS' : ''
		,'REGEXPS' : {
			'attributes': 'color: #B1AC41;'
			,'tags': 'color: #E62253;'
			,'xml': 'color: #8DCFB5;'
			,'cdata': 'color: #50B020;'
		}	
	}		
};
