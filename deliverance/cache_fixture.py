
from paste.response import replace_header
from paste.httpheaders import IF_MODIFIED_SINCE, EXPIRES, CONTENT_LENGTH, ETAG

class CacheFixtureResponseInfo(object): 
    def __init__(self, data, mod_time=None, 
                 etag=None, cache_control=None, 
                 expires=None): 
        self.data = data
        self.mod_time = mod_time
        self.etag = etag
        self.cache_control = cache_control 
        self.expires = expires

class CacheFixtureApp(object):
    """
    a crumby app that can be set up with 
    dummy content for different urls and 
    be configured with a variety of responses when 
    cache related headers are present in the request. 

    responds with a 404 for any url not explicitly 
    mapped in. 
    """
    def __init__(self): 
        self.responses = {}

    def map_url(self, path, response_info): 
        self.responses[path] = response_info

    def get_response_info(self, path): 
        return self.responses.get(path, None)

    def __call__(self, environ, start_response): 
        path = environ['PATH_INFO']

        if path in self.responses: 
            response_info = self.responses[path]
            
            headers = self.calc_headers(response_info)

            if response_info.mod_time is not None and 'HTTP_IF_MODIFIED_SINCE' in environ: 
                req_time = IF_MODIFIED_SINCE.parse(environ['HTTP_IF_MODIFIED_SINCE'])

                if req_time > response_info.mod_time: 
                    replace_header(headers, 'content-length', '0')
                    start_response('304 Not Modified', headers)
                    return []

            if response_info.etag is not None and 'HTTP_IF_NONE_MATCH' in environ: 
                # XXX this expects only one etag, but it could be more than one
                req_etag = environ['HTTP_IF_NONE_MATCH']
                if response_info.etag == req_etag: 
                    replace_header(headers, 'content-length', '0')
                    start_response('304 Not Modified', headers)
                    return []

            headers.append(('content-length', str(len(response_info.data))))
            headers.append(('content-type', 'text/html'))        

            start_response('200 OK', headers)
            return [response_info.data]

        else:
            start_response('404 Not Found', [('content-length','0')])
            return []

    def calc_headers(self, response_info):
        headers = []

        if response_info.etag is not None: 
            replace_header(headers, 'etag', response_info.etag)
        if response_info.cache_control is not None: 
            headers.add(('cache-control', response_info.cache_control))
        if response_info.expires is not None: 
            EXPIRES.update(headers,'expires', time=response_info.expires)

        return headers
