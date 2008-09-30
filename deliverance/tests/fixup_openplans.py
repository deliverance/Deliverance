import urlparse
import posixpath

def fixup_openplans_response(request, response, orig_base, proxied_base, proxied_url, log):
    user_base = 'https://www.openplans.org/people'
    if response.location and response.location.startswith(user_base + '/'):
        print 'incoming: %s (%r)' % (response.location, request.application_url)
        user_rest = response.location[len(user_base):]
        location = posixpath.join('/people', user_rest.lstrip('/'))
        response.location = urlparse.urljoin(request.application_url, location)
        print 'outgoing: %s' % response.location, [location, user_rest]

