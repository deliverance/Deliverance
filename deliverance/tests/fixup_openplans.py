def fixup_openplans_response(request, response, orig_base, proxied_base, proxied_url, log):
    user_base = 'http://www.openplans.org/people'
    if response.location and response.location.startswith(user_base + '/'):
        user_rest = response.location[len(user_base):]
        response.location = '%s/people%s' % (request.application_url, user_rest)

