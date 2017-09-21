"""
Restful json clients.

Use `Resource`_ for a connection to a single host.
Use `Pool`_ for persistent thread-safe connections to a single host.
Use `Resources`_ for multiple hosts with simple partitioning or replication.

`Resources`_ optionally reuse connections, handling request timeouts.
Broadcasting to multiple resources is parallelized with asynchronous requests and responses.

The load balancing strategy is randomized, biased by the number of cached connections available.
This inherently provides limited failover support, but applications must still handle exceptions as desired.
"""

from future_builtins import zip
import warnings
import random
import collections
import io
import gzip
import shutil
import httplib
import urllib
import urlparse
import errno
from .utils import json, suppress


class Response(httplib.HTTPResponse):
    "A completed response which handles json and caches its body."
    content_type = 'application/json'

    def end(self):
        self.body = self.read()
        self.time = float(self.getheader('x-response-time', 'nan'))
        if 'gzip' in self.getheader('content-encoding', ''):
            self.body = gzip.GzipFile(fileobj=io.BytesIO(self.body)).read()

    def __nonzero__(self):
        "Return whether status is successful."
        return httplib.OK <= self.status < httplib.MULTIPLE_CHOICES

    def __call__(self):
        "Return evaluated response body or raise exception."
        body = self.body
        if body and self.getheader('content-type').startswith(self.content_type):
            body = json.loads(body)
        code, agent, text = self.getheader('warning', '  ').split(' ', 2)
        if agent == 'lupyne':
            warnings.warn(json.loads(text))
        if self:
            return body
        raise httplib.HTTPException(self.status, self.reason, body)


class Resource(httplib.HTTPConnection):
    "Synchronous connection which handles json responses."
    response_class = Response
    headers = {'accept-encoding': 'compress, gzip', 'content-length': '0'}

    def request(self, method, path, body=None):
        "Send request after handling body and headers."
        headers = dict(self.headers)
        if body is not None:
            body = json.dumps(body)
            headers.update({'content-length': str(len(body)), 'content-type': self.response_class.content_type})
        httplib.HTTPConnection.request(self, method, path, body, headers)

    def getresponse(self, filename=''):
        "Return completed response, optionally write response body to a file."
        response = httplib.HTTPConnection.getresponse(self)
        if response and filename:
            with open(filename, 'w') as output:
                shutil.copyfileobj(response, output)
        response.end()
        return response

    def call(self, method, path, body=None, params=(), redirect=False):
        "Send request and return completed `response`_."
        if params:
            path += '?' + urllib.urlencode(params, doseq=True)
        self.request(method, path, body)
        response = self.getresponse()
        if redirect and httplib.MULTIPLE_CHOICES <= response.status < httplib.NOT_MODIFIED:
            url = urlparse.urlparse(response.getheader('location'))
            assert url.netloc.startswith(self.host)
            warnings.warn('{}: {}'.format(response.reason, url.path), DeprecationWarning)
            return self.call(method, url.path, body, params, redirect - 1)
        return response

    def download(self, path, filename):
        "Download response body from GET request to a file."
        self.request('GET', path)
        return self.getresponse(filename)()

    def multicall(self, *requests):
        "Pipeline requests (method, path[, body]) and generate completed responses."
        responses = []
        for request in requests:
            self.request(*request)
            responses.append(self.response_class(self.sock, self.debuglevel, self.strict, self._method))
            self._HTTPConnection__state = 'Idle'
        return (response.begin() or response.end() or response for response in responses)

    def get(self, path, **params):
        "Return response body from GET request."
        return self.call('GET', path, params=params)()
    def post(self, path, body=None, **kwargs):
        "Return response body from POST request."
        return self.call('POST', path, body, **kwargs)()
    def put(self, path, body=None, **kwargs):
        "Return response body from PUT request."
        return self.call('PUT', path, body, **kwargs)()
    def delete(self, path, **params):
        "Return response body from DELETE request."
        return self.call('DELETE', path, params=params)()
    def patch(self, path, body=None, **kwargs):
        "Return response body from PATCH request."
        return self.call('PATCH', path, body, **kwargs)()


if hasattr(httplib, 'HTTPSConnection'):  # pragma: no branch
    class SResource(Resource, httplib.HTTPSConnection, object):
        pass


class Pool(collections.deque):
    "Thread-safe resource pool for one host."
    resource_class = Resource

    def __init__(self, host, limit=0):
        collections.deque.__init__(self, maxlen=limit)
        self.host = host

    def stream(self, method, path, body=None):
        "Generate resource, initial response, and final response while handling timeouts."
        try:
            resource = self.popleft()
        except IndexError:
            resource = self.resource_class(self.host)
        resource.request(method, path, body)
        response = yield resource
        with suppress(httplib.BadStatusLine, IOError, errno=errno.ECONNRESET):
            response = resource.getresponse()
            timeout = response.status == httplib.BAD_REQUEST and response.body == 'Illegal end of headers.'
        if response is None or response.status == httplib.REQUEST_TIMEOUT or timeout:
            resource.close()
            resource.request(method, path, body)
            yield response
            yield resource.getresponse()
        else:
            self.append(resource)
            yield response
            yield response

    def call(self, method, path, body=None):
        "Send request and return completed `response`_."
        return list(self.stream(method, path, body))[-1]


class Resources(dict):
    """Thread-safe mapping of hosts to resource pools.
    
    :param hosts: host[:port] strings
    :param limit: maximum number of cached resources per host
    """
    def __init__(self, hosts, limit=0):
        self.update((host, Pool(host, limit)) for host in hosts)

    def priority(self, host):
        "Return priority for host.  None may be used to eliminate from consideration."
        return -len(self[host])

    def choice(self, hosts):
        "Return chosen host according to priority."
        priorities = collections.defaultdict(list)
        for host in hosts:
            priorities[self.priority(host)].append(host)
        priorities.pop(None, None)
        return random.choice(priorities[min(priorities)])

    def unicast(self, method, path, body=None, hosts=()):
        "Send request and return `response`_ from any host, optionally from given subset."
        host = self.choice(tuple(hosts) or self)
        return self[host].call(method, path, body)

    def broadcast(self, method, path, body=None, hosts=()):
        "Send requests and return responses from all hosts, optionally from given subset."
        hosts = tuple(hosts) or self
        streams = [self[host].stream(method, path, body) for host in hosts]
        return list(zip(*streams))[-1]
