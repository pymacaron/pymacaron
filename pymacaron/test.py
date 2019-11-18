import os
from pymacaron_unit import testcase


def load_port_host_token():
    """Find out which host:port to run acceptance tests against,
    using the environment variables PYM_SERVER_HOST, PYM_SERVER_PORT
    """

    server_host, server_port, token = (None, None, None)

    if 'PYM_SERVER_HOST' in os.environ:
        server_host = os.environ['PYM_SERVER_HOST']
    if 'PYM_SERVER_PORT' in os.environ:
        server_port = os.environ['PYM_SERVER_PORT']

    token = os.environ.get('PYM_JWT_TOKEN', None)

    if server_host:
        if server_host.startswith('http://'):
            server_host = server_host[7:]
        if server_host.startswith('https://'):
            server_host = server_host[8:]
        if server_host.endswith('/'):
            server_host = server_host[:-1]

    if not server_host or not server_port:
        raise Exception("Please set both of PYM_SERVER_HOST and PYM_SERVER_PORT envvironment variables")

    return (server_host, server_port, token)


class PyMacaronTestCase(testcase.PyMacaronTestCase):

    token = None

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        self.host, self.port, self.token = load_port_host_token()
        proto = 'https' if self.port in (443, '443') else 'http'
        self.base_url = '%s://%s:%s' % (proto, self.host, self.port)

    def assertIsVersion(self, j):
        self.assertTrue(type(j['version']) is str)
        self.assertTrue(type(j['name']) is str)
        self.assertTrue(type(j['container']) is str)
        self.assertTrue(type(j['pym_env']) is str)

    def assertHasPing(self):
        return self.assertGetReturnOk('ping')

    def assertHasVersion(self, verify_ssl=True):
        j = self.assertGetReturnJson('version', 200, verify_ssl=verify_ssl)
        self.assertIsVersion(j)
        return j

    def assertHasAuthVersion(self, verify_ssl=True):
        self.assertGetReturnError('auth/version', 401, 'AUTHORIZATION_HEADER_MISSING', verify_ssl=verify_ssl)

        tests = [
            # header,  status code, json code
            ("", 401, 'AUTHORIZATION_HEADER_MISSING'),
            ("Bearer1234567890", 401, 'TOKEN_INVALID'),
            ("bearer foo bar", 401, 'TOKEN_INVALID'),
            ("Bearer 1234567890", 401, 'TOKEN_INVALID'),
        ]

        for t in tests:
            token, status, error = t
            self.assertGetReturnError('auth/version', status, error, token, verify_ssl=verify_ssl)

        j = self.assertGetReturnJson('auth/version', 200, "Bearer %s" % self.token, verify_ssl=verify_ssl)
        self.assertIsVersion(j)
        return j
