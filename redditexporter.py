#!/usr/bin/env python

import sys
import json
import time
import urllib
from urllib import urlencode
from urlparse import urlparse, urlunparse, parse_qs

from xml.sax.saxutils import escape as escape_html
from xml.sax.saxutils import unescape as unescape_html

header_template = '''
<html lang="en">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/> 
    <link REL="SHORTCUT ICON" HREF="http://www.reddit.com/favicon.ico">
    <title>Exported links from %(exported_url)s</title>
    <style type="text/css">
      .selftext {
        border: 1px dashed;
      }
    </style>
  </head>
  <body>
    <ol>
'''.strip()
link_template = '''
<li class="link">
  <h1><a href="%(url)s">%(title)s</a></h1>
  (<a href="%(domain_link)s">%(domain)s</a>)
  submitted by <a href="http://www.reddit.com/user/%(author)s">%(author)s</a>
  to <a href="http://www.reddit.com/r/%(subreddit)s">%(subreddit)s</a>
  %(score)d points
  at <tt>%(date)s</tt>
  (<a href="http://www.reddit.com/r/%(subreddit)s/comments/%(id)s">%(num_comments)d comments</a>,
   <a href="http://www.reddit.com/tb/%(id)s">toolbar</a>)
  %(selftext_template)s
</li>
'''.strip()
selftext_template = '''<div class="selftext"">%s</div>'''
footer_template = '''
    </ol>
  </body>
</html>
'''.strip()

# please don't hurt reddit
fetch_size = 100     # the higher the better, but reddit ignores +100
sleep_time = 1       # in seconds. how long to sleep between
                     # requests. higher is better
request_limit = None # how many requests to make to reddit before
                     # stopping (set to None to disable)

debug = False

def get_links(sourceurl, requests = 0):
    '''
    Given a reddit JSON URL, yield the JSON Link API objects,
    following 'after' links
    '''
    # rip apart the URL, make sure it has .json at the end, and set
    # the limit
    scheme, host, path, params, query, fragment = urlparse(sourceurl)

    parsed_params = parse_qs(query) if query else {}
    parsed_params['limit'] = [fetch_size]
    fragment = None # erase the fragment, we don't use it
    assert path.endswith('.json') or path.endswith('/')
    if path.endswith('/'):
        path = path + '.json'

    new_urltuple = (scheme, host, path, params,
                    urlencode(parsed_params, doseq = True), fragment)
    composed_sourceurl = urlunparse(new_urltuple)

    if debug:
        sys.stderr.write('fetching %s\n' % composed_sourceurl)

    text = urllib.urlopen(composed_sourceurl).read()
    parsed = json.loads(text)

    # there may be multiple listings, like on a comments-page, but we
    # can only export from pages with one listing
    assert parsed['kind'] == 'Listing'

    listing = parsed['data']

    for child in listing.get('children', []):
        yield child

    if (listing.get('after', None)
        and (request_limit is None
             or requests < request_limit - 1)):
        after_parsed_params = parsed_params.copy()
        after_parsed_params['after'] = [listing['after']]
        after_urltuple = (scheme, host, path, params,
                          urlencode(after_parsed_params, doseq = True),
                          fragment)
        after_sourceurl = urlunparse(after_urltuple)

        time.sleep(sleep_time)

        # yes, this is recursive, but if you're making enough requests
        # to blow out your stack, you're probably hurting reddit
        for link in get_links(after_sourceurl, requests+1):
            yield link

def main(sourceurl):
    '''
    Given a reddit JSON url, yield unicode strings that represent the
    exported HTML
    '''
    yield header_template % dict(exported_url = escape_html(sourceurl))

    for link in get_links(sourceurl):
        if link['kind'] != 't3':
            # skip non-links. support for comments can be added later
            # if someone cares enough
            continue

        data = link['data']

        template_data = dict(
            id = escape_html(data['id']),
            url = escape_html(data['url']),
            title = escape_html(data['title']),
            domain = escape_html(data['domain']),
            author = escape_html(data['author']),
            subreddit = escape_html(data['subreddit']),
            score = int(data['score']),
            num_comments = int(data['num_comments']),
            date = time.ctime(data['created_utc']),
            selftext_template = '',
            )

        if data['domain'].startswith('self.') and data['url'].startswith('http://www.reddit.com/'):
            # This is the only way to tell if it's a self-post from
            # the API :-/
            template_data['domain_link'] = (
                'http://www.reddit.com/r/%(subreddit)s'
                % dict(subreddit = escape_html(data['subreddit'])))
        else:
            template_data['domain_link'] = (
                'http://www.reddit.com/domain/%(domain)s'
                % dict(domain = escape_html(data['domain'])))

        if data.get('selftext_html'):
            selftext = selftext_template % unescape_html(data['selftext_html'])
            template_data['selftext_template'] = selftext

        yield link_template % template_data

    yield footer_template


if __name__=='__main__':
    for s in main(sys.argv[1]):
        sys.stdout.write(s.encode('utf-8'))
