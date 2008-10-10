"""
Logging for deliverance.

This does not use the standard :mod:`logging` module because that
module is not easily applied and inspected locally.  We want the log
messages to be strictly per-request.
"""

import logging
from lxml.etree import tostring, _Element
from tempita import HTMLTemplate, html_quote, html
from deliverance.security import display_logging, edit_local_files

NOTIFY = (logging.INFO + logging.WARN) / 2

logging.addLevelName(NOTIFY, 'NOTIFY')

class SavingLogger(object):
    """
    Logger that saves all its messages locally.
    """
    def __init__(self, request, middleware):
        self.messages = []
        self.middleware = middleware
        self.request = request
        # This is writable:
        self.theme_url = None
        # Also writable (list of (url, name))
        self.edit_urls = []

    def message(self, level, el, msg, *args, **kw):
        """Add one message at the given log level"""
        if args:
            msg = msg % args
        elif kw:
            msg = msg % kw
        self.messages.append((level, el, msg))
        return msg
    def debug(self, el, msg, *args, **kw):
        """Log at the DEBUG level"""
        return self.message(logging.DEBUG, el, msg, *args, **kw)
    def info(self, el, msg, *args, **kw):
        """Log at the INFO level"""
        return self.message(logging.INFO, el, msg, *args, **kw)
    def notify(self, el, msg, *args, **kw):
        """Log at the NOTIFY level"""
        return self.message(NOTIFY, el, msg, *args, **kw)
    def warn(self, el, msg, *args, **kw):
        """Log at the WARN level"""
        return self.message(logging.WARN, el, msg, *args, **kw)
    warning = warn
    def error(self, el, msg, *args, **kw):
        """Log at the ERROR level"""
        return self.message(logging.ERROR, el, msg, *args, **kw)
    def fatal(self, el, msg, *args, **kw):
        """Log at the FATAL level"""
        return self.message(logging.FATAL, el, msg, *args, **kw)

    def finish_request(self, req, resp):
        """Called by the middleware at the end of the request.

        This gives the log an opportunity to add information to the
        page.
        """
        if 'deliv_log' in req.GET and display_logging(req):
            resp.body += self.format_html_log()
            resp.cache_expires()
        return resp

    log_template = HTMLTemplate('''\
    <H1 style="border-top: 3px dotted #f00">Deliverance Information</h1>

    <div>
      {{if log.theme_url}}
        <a href="{{theme_url}}" target="_blank">theme</a>
      {{else}}
        theme: no theme set
      {{endif}}
      | <a href="{{unthemed_url}}" target="_blank">unthemed content</a>
      | <a href="{{content_source}}" target="_blank">content source</a>
      | <a href="{{content_browse}}" target="_blank">browse content</a>
        / <a href="{{theme_browse}}" target="_blank">theme</a>
      {{if log.edit_urls}}
      | <select onchange="if (this.value) {window.open(this.value, '_blank')}; this.selectedIndex=0;">
          <option value="">edit location</option>
        {{for url, name in log.edit_urls}}
          <option value="{{url}}">{{name}}</option>
        {{endfor}}
        </select>
      {{endif}}
      {{if edit_rules}}
      | <a href="{{edit_rules}}" target="_blank">edit rules</a>
      {{endif}}
    </div>

    {{if log.messages}}
      {{div}}
      {{h2}}Log</h2>
      {{div_inner}}
      <table>
          <tr>
            <th>Level</th><th>Message</th><th>Context</th>
          </tr>
        {{for level, level_name, el, message in log.resolved_messages():}}
          {{py:color, bgcolor = log.color_for_level(level)}}
          <tr style="color: {{color}}; background-color: {{bgcolor}}; vertical-align: top">
            {{td}}{{level_name}}</td>
            {{td}}{{message}}</td>
            {{td}}{{log.obj_as_html(el) | html}}</td>
          </tr>
        {{endfor}}
      </table>
      </div></div>
    {{else}}
      {{h2}}No Log Messages</h2>
    {{endif}}
    ''', name='deliverance.log.SavingLogger.log_template')
     
    tags = dict(
        h2=html('<h2 style="color: #000; background-color: #f90; margin-top: 0; '
                'border-bottom: 1px solid #630">'),
        div=html('<div style="border: 2px solid #000; margin-bottom: 1em">'),
        div_inner=html('<div style="padding: 0.25em">'),
        td=html('<td style="margin-bottom: 0.25em; '
                'border-bottom: 1px solid #ddd; padding-right: 0.5em">'),
        )

    def format_html_log(self):
        """Formats this log object as HTML"""
        content_source = self.link_to(self.request.url, source=True)
        content_browse = self.link_to(self.request.url, browse=True)
        theme_browse = self.link_to(self.theme_url, browse=True)
        if edit_local_files(self.request.environ):
            ## FIXME: also test for the local-ness of the file
            edit_rules = (self.request.environ['deliverance.base_url']
                          + '/.deliverance/edit_rules')
        else:
            edit_rules = None
        return self.log_template.substitute(
            log=self, middleware=self.middleware, 
            unthemed_url=self._add_notheme(self.request.url),
            theme_url=self._add_notheme(self.theme_url),
            content_source=content_source,
            content_browse=content_browse, theme_browse=theme_browse,
            edit_rules=edit_rules,
            **self.tags)

    def _add_notheme(self, url):
        """Adds the necessary query string argument to the URL to suppress
        theming"""
        if url is None:
            return None
        if '?' in url:
            url += '&'
        else:
            url += '?'
        return url + 'deliv_notheme'

    def resolved_messages(self):
        """
        Yields a list of ``(level, level_name, context_el, rendered_message)``
        """
        for level, el, msg in self.messages:
            level_name = logging.getLevelName(level)
            yield level, level_name, el, msg

    def obj_as_html(self, el):
        """
        Returns the object formatted as HTML.  This is used to show
        the context in log messages.
        """
        ## FIXME: another magic method?
        if hasattr(el, 'log_description'):
            return el.log_description(self)
        elif isinstance(el, _Element):
            return html_quote(tostring(el))
        else:
            return html_quote(unicode(el))

    def color_for_level(self, level):
        """
        The HTML foreground/background colors for a given level.
        """
        return {
            logging.DEBUG: ('#666', '#fff'),
            logging.INFO: ('#333', '#fff'),
            NOTIFY: ('#000', '#fff'),
            logging.WARNING: ('#600', '#fff'),
            logging.ERROR: ('#fff', '#600'),
            logging.CRITICAL: ('#000', '#f33')}[level]

    def link_to(self, url, source=False, line=None, selector=None, browse=False):
        """
        Gives a link to the given source view (just routes to
        `deliverance.middleware.DeliveranceMiddleware.link_to`).
        """
        return self.middleware.link_to(self.request, url, source=source, line=line, 
                                       selector=selector, browse=browse)

class PrintingLogger(SavingLogger):
    """Logger that saves messages, but also prints out messages
    immediately"""

    def __init__(self, request, middleware, print_level=logging.DEBUG):
        super(PrintingLogger, self).__init__(request, middleware)
        self.print_level = print_level

    def message(self, level, el, msg, *args, **kw):
        """Add one message at the given log level"""
        msg = super(PrintingLogger, self).message(level, el, msg, *args, **kw)
        if level >= self.print_level:
            if isinstance(el, _Element):
                s = tostring(el)
            else:
                s = str(el)
            print '%s (%s)' % (msg, s)
        return msg
