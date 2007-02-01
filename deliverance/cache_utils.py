import re
from paste.response import header_value, replace_header
from paste.httpheaders import EXPIRES 
from time import time as now
from sets import Set


"""
utilities for fusing cache related HTTP headers from 
multiple sources 

XXX there is probably a good amount of work in here 
that Paste could simplify 

TODO: 
handle expires 
handle last-modified
"""


def merge_cache_headers(self, response_info, new_headers): 
    """
    replaces cache related headers in new_headers 
    with caching info calculated cache_info 
    (a map of urls to wsgi response triples) 
    """

    headers_map = {}
    for uri, response in response_info.items(): 
        headers_map[uri] = response[1]
        
    cache_control_map = merge_cache_control(headers_map.values(), upgrade_expires=True)
    if len(cache_control_map):         
        replace_header(new_headers, 'cache-control', 
                       flatten_directive_map(cache_control_map))
        # provide an Expires header if there is a cache-control max-age 
        if 'max-age' in cache_control_map: 
            expire_delta = int(new_cache_ctl['max-age'])
            EXPIRES.update(new_headers, delta=expire_delta)

    etag = merge_etags_from_headers(headers_map)
    if etag is not None: 
        replace_header(new_headers, 'etag', etag )

    vary = merge_vary_from_headers(headers_map)
    if vary is not None: 
        replace_header(new_headers, 'vary', vary)



def merge_cache_control(header_sets, upgrade_expires=False): 
    """
    computes a value for the cache-control header based on the 
    values of the cache-control headers found in the list of 
    wsgi-style response header lists. returns a map of 
    cache-control directive names to values. use 
    flatten_directive_map to compute value suitable for 
    the cache-control header. 
    
    if upgrade_expires is True, if there is a header set with 
    an Expires header, but no cache-control header, it is treated as a 
    cache-control: public, max-age: <expire difference from now>  

    >>> headerses = []
    >>> headerses.append([ ('cache-control', "public, max-age = 10") ])
    >>> headerses.append([ ('cache-control', "public, max-age = 5") ])
    >>> headerses.append([ ('cache-control', "public, max-age = 2") ])
    >>> flatten_directive_map(merge_cache_control(headerses))
    'public, max-age = 2'

    >>> headerses = []
    >>> headerses.append([ ('cache-control', "public, max-age = 10") ])
    >>> headerses.append([ ('cache-control', "private, max-age = 5") ])
    >>> headerses.append([ ('cache-control', "public, max-age = 2") ])
    >>> flatten_directive_map(merge_cache_control(headerses))
    'private, max-age = 2'

    >>> headerses = [[],[('cache-control', "public, max-age = 100")]]
    >>> from paste.httpheaders import EXPIRES
    >>> EXPIRES.update(headerses[0], time=( int(now()) + 20))
    >>> flatten_directive_map(merge_cache_control(headerses, upgrade_expires=True))
    'public, max-age = 20'
    

    """    

    cache_ctls = [parse_cache_directives(header_value(x,'cache-control')) for x in header_sets]

    if upgrade_expires: 
        # if there is a header set with no cache-control, but an Expires, 
        # upgrade it to a cache-control: max-age = <expires offset>, public
        for i,cc in enumerate(cache_ctls):
            if len(cc) == 0:
                expire_val = header_value(header_sets[i],'expires')
                if expire_val is not None:
                    expire_secs = int(EXPIRES.parse(expire_val) - int(now()))
                    cc['public'] = None
                    cc['max-age'] = expire_secs
        
    # apply cache-control merging policies 
    new_cache_ctl = dict() 
    merge_if_all('public',new_cache_ctl, cache_ctls)
    merge_if_any('private',new_cache_ctl, cache_ctls) 
    merge_if_any('private',new_cache_ctl, cache_ctls) 
    merge_if_any('no-cache',new_cache_ctl, cache_ctls)
    merge_if_any('no-store',new_cache_ctl, cache_ctls)
    merge_if_any('no-transform', new_cache_ctl, cache_ctls)
    merge_if_any('must-revalidate', new_cache_ctl, cache_ctls)
    merge_if_any('proxy-revalidate', new_cache_ctl, cache_ctls) 
    merge_minimum('max-age', new_cache_ctl, cache_ctls)
    merge_minimum('smax-age', new_cache_ctl, cache_ctls)

    return new_cache_ctl 

    
def merge_etags_from_headers(headers_map): 
    """
    accepts a map from uris to wsgi-style header lists 
    returns the value for the etag merged from all 
    etag headers present in the header lists 
    """
    etag_map = {}
    for uri, headers in headers_map.items(): 
        etag = header_value(headers,'etag')
        if etag is not None and len(etag) != 0: 
            etag_map[uri] = etag
    return merge_etags(etag_map)
    

def merge_vary_from_headers(headers_map): 
    """
    XXX set ordering 
    >>> d = {'a': [ ('Vary', '"foo, bar"') ], 'b': [ ('Vary', '"bar, quux"') ]}
    >>> merge_vary_from_headers(d)
    '"quux, foo, bar"'

    >>> d = {}
    >>> v = merge_vary_from_headers(d)
    >>> v is None
    True

    """
    vary_fields = Set()
    for val in [ header_value(x, 'vary') for x in headers_map.values() ]: 
        vary_fields.update(parse_fieldname_list(val))

    if len(vary_fields): 
        return '\"%s\"' % ', '.join(vary_fields)
    else: 
        return None

def parse_merged_etag(composite_tag): 
    """
    given a composite etag computed by merge_etags, 
    computes a map from resource identifiers to 
    respective etags 

    >>> d = parse_merged_etag('deliverance:apple,15,some_apple_etag,orange,16,some_orange_etag')
    >>> print_sorted_dict(d)
    {'apple': 'some_apple_etag', 'orange': 'some_orange_etag'}


    >>> d = parse_merged_etag('some_raND0m_g0bbl7+yGook')
    >>> d
    {}

    >>> d = parse_merged_etag('deliverance:some_,99,ra,ND0m_g0,bb,l7+yGook')
    >>> d
    {}

    """
    if not composite_tag.startswith('deliverance:'): 
        return {}

    tags = dict(); 

    composite_tag = composite_tag[len('deliverance:'):]
    while len(composite_tag) > 0: 
        resource,composite_tag = pop_et_token(composite_tag)
        if resource is None:
            return tags 
        tag_len, composite_tag = pop_et_token(composite_tag)
        if tag_len is None:             
            return tags
        try:
            tag_len = int(tag_len)
        except: 
            return {}
        
        if len(composite_tag) >= tag_len: 
            tags[resource] = composite_tag[:tag_len]
            composite_tag = composite_tag[tag_len+1:]
        else:
            return {}

    return tags 
    

    
#############
# helpers 
############# 


def pop_et_token(ctag): 
    """
    finds the first comma separated token, returns a tuple 
    containing the token and the rest of the string given 
    
    >>> pop_et_token("abc,def,ghi")
    ('abc', 'def,ghi')
    """
    sep = ctag.find(',')
    if sep == -1:    
        return (None,ctag)
    else:
        return (ctag[:sep],ctag[sep+1:])




CSL_QUOTE_PAT = '".*?"'
def parse_header_list(hval): 
    """
    split comma separated list into elements, ignoring quoted 
    commas. 
    eg: 
    
    >>> parse_header_list('max-age = 10, public')
    ['max-age = 10', 'public']
    
    >>> parse_header_list('max-age = 10, public = "foo, bar"')
    ['max-age = 10', 'public = "foo, bar"']
    
    >> parse_header_list('public')
    ['public']
    """
    quoted_strings = re.findall(CSL_QUOTE_PAT,hval)
    no_quote_val = re.sub(CSL_QUOTE_PAT,'?',hval)
    vals = [x.strip() for x in no_quote_val.split(',')]
    
    for i,val in enumerate(vals): 
        qpos = val.find('?')
        if qpos != -1: 
            vals[i] = val.replace('?',quoted_strings.pop())

    return vals
       
    
def parse_cache_directive(directive): 
    """
    returns a tuple for the directive containing the name of 
    the directive and a list of arguments. eg:  

    >>> parse_cache_directive('foo = 10') 
    ('foo', '10')
    
    >>> parse_cache_directive('foo = "bar"')
    ('foo', '"bar"')
    
    >>> parse_cache_directive('foo = "bar, quux, baz"')
    ('foo', '"bar, quux, baz"')
    
    >>> parse_cache_directive("foo")
    ('foo', None)
    """
    split = directive.find('=')
    if (split == -1): 
        return (directive,None)
    else:
        return (directive[0:split].strip(), 
                directive[split+1:].strip())

def parse_fieldname_list(val): 
    """
    parses directive value(s) into a list, eg: 
    
    >>> parse_fieldname_list('foo')
    ['foo']

    >>> parse_fieldname_list('"foo"')
    ['foo']

    >>> parse_fieldname_list('"foo, bar,quux"')
    ['foo', 'bar', 'quux']

    >>> parse_fieldname_list('""')
    []

    >>> parse_fieldname_list(None)
    []
    """

    if val is None: 
        return [] 

    if val.startswith('"'): 
        val = val[1:]
    if val.endswith('"'): 
        val = val[:-1]
    val = val.strip()

    if len(val) == 0: 
        return []    

    return [x.strip().lower() for x in val.split(',')]
    

def parse_cache_directives(hval): 
    """
    returns a dict mapping directives to raw values  
     
    >>> print_sorted_dict(parse_cache_directives('max-age = 10, public'))
    {'max-age': '10', 'public': None}
    
    >>> print_sorted_dict(parse_cache_directives('max-age = 10, public = "foo, bar"'))
    {'max-age': '10', 'public': '"foo, bar"'}
    """
    if hval is None: 
        return {}

    dirs = dict()
    for (name,val) in [parse_cache_directive(x) for x in parse_header_list(hval)]: 
        dirs[name] = val
    return dirs 

def merge_expire_header(cc, headers): 
    """
    this reformulates any expire header in headers and 
    places an equivalent cache-control header in cc 
    """
    pass 

def merge_etags(etag_map): 
    """
    given a map of resource identifiers to etags, 
    computes a composite etag 

    XXX dict ordering 
    >>> d = {'apple': 'some_apple_etag', 'orange': 'some_orange_etag'}
    >>> merge_etags(d) 
    'deliverance:orange,16,some_orange_etag,apple,15,some_apple_etag'
    """
    if etag_map is None or len(etag_map) == 0:
        return None

    composite_etag="deliverance:"

    for k,v in etag_map.items(): 
        composite_etag += "%s,%d,%s," % (k,len(v),v)
    composite_etag = composite_etag[:-1]
    return composite_etag 
    

        
def merge_if_all(directive, newcc, cc): 
    """
    puts the directive given in the new cache-control 
    directives newcc if the directive appears in all 
    sets of directives cc 

    expects cc is a list of dicts of the form produced by 
    parse_cache_directives 
    eg: 

    >>> d = dict()
    >>> ccs = [{'public': None, 'max-age': '10'}, {'public': None, 'max-age': '20'}]
    >>> merge_if_all('public',d,ccs)
    >>> d
    {'public': None}

    >>> d = dict()
    >>> ccs = [{'public': None, 'max-age': '10'}, {'max-age': '20'}]
    >>> merge_if_all('public', d, ccs)
    >>> d
    {}
    """
    for c in cc:         
        if not c.has_key(directive): 
            return 
    newcc[directive] = None

def merge_if_any(directive, newcc, cc): 
    """
    puts the directive given in the new cache-control 
    directives newcc if the directive appears in any of 
    the sets of directives cc. merges any fieldname 
    lists that appear in cc for the directive. if any 
    instance has no fieldnames, no fieldnames are used 
    in the output. 

    expects cc is a list of dicts of the form produced by 
    parse_cache_directives 

    >>> d = dict()
    >>> ccs = [{'private': None, 'max-age': '10'}, {'max-age': '20'}]
    >>> merge_if_any('private', d, ccs)
    >>> d
    {'private': None}

    >>> d = dict()
    >>> ccs = [{'private': '"foo, bar"', 'max-age': '10'}, {'max-age': '9'}, {'private': '"quux, bar"'}]
    >>> merge_if_any('private', d, ccs)
    >>> d
    {'private': '"quux, foo, bar"'}

    >>> d = dict()
    >>> ccs = [{'private': '"foo, bar"', 'max-age': '10'}, {'max-age': '20'}, {'private': None}]
    >>> merge_if_any('private', d, ccs)
    >>> d
    {'private': None}

    """
    present = False 
    field_set = Set()

    for c in cc: 
        if c.has_key(directive): 
            present = True
            if c[directive] is not None:
                if field_set is not None: 
                    field_set.update(parse_fieldname_list(c[directive]))
            else:
                field_set = None

    if present:
        if field_set and len(field_set):             
            newcc[directive] = '"' + ', '.join(field_set) + '"'
        else:
            newcc[directive] = None

def merge_minimum(directive, newcc, cc): 
    """ 
    puts the minimum value specified for the directive 
    among all instances of the directive in the set cc
    into the dict newcc. 
    if the directive does not appear in a particular 
    set, the value is not placed in newcc. 
    
    expects cc is a list of dicts of the form produced by 
    parse_cache_directives 

    >>> d = dict()
    >>> ccs = [{'max-age': '10'}, {'max-age': '20'} ]
    >>> merge_minimum('max-age', d, ccs)
    >>> d
    {'max-age': '10'}

    >>> d = dict()
    >>> ccs = [{'max-age': '10'}, {'smax-age': '20'} ]
    >>> merge_minimum('max-age', d, ccs)
    >>> d
    {}
    """

    if len(cc) == 0:
        return 

    if cc[0].has_key(directive): 
        min = int(cc[0][directive])
    else: 
        return 

    for c in cc: 
        if c.has_key(directive): 
            dval = int(c[directive])
            if dval < min:
                min = dval 
        else: 
            return

    newcc[directive] = str(min)

def flatten_directive_map(d): 
    """ 
    flattens a map of directive -> fieldnames 
    back into the HTTP comma separated list 
    form suitable as a value for the 
    cache-control header 
    """ 
    dstr = ''
    last = len(d) -1
    for i, k in enumerate(d.keys()): 
        dstr += k 
        if d[k]: 
            dstr += ' = %s' % d[k]
        if (i != last): 
            dstr += ', '

    return dstr


#########################
# just test support 
#########################

def print_sorted_dict(d): 
    keys = d.keys()
    keys.sort()
    last = len(keys)-1
    dstr = '{'
    for i, k in enumerate(keys): 
        dstr += "%s: %s" % (k.__repr__(), d[k].__repr__())
        if i < last: 
            dstr += ', '
    dstr += '}'
    print dstr 

 
def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()
