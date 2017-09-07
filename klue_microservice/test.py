import os
from klue_unit.testcase import KlueTestCase


def load_port_host_token():
    """Find out which host:port to run acceptance tests against,
    using the environment variables KLUE_SERVER_HOST, KLUE_SERVER_PORT
    """

    server_host, server_port, token = (None, None, None)

    if 'KLUE_SERVER_HOST' in os.environ:
        server_host = os.environ['KLUE_SERVER_HOST']
    if 'KLUE_SERVER_PORT' in os.environ:
        server_port = os.environ['KLUE_SERVER_PORT']

    token = os.environ.get('KLUE_JWT_TOKEN', None)

    if server_host:
        if server_host.startswith('http://'):
            server_host = server_host[7:]
        if server_host.startswith('https://'):
            server_host = server_host[8:]
        if server_host.endswith('/'):
            server_host = server_host[:-1]

    if not server_host or not server_port:
        raise Exception("Please set both of KLUE_SERVER_HOST and KLUE_SERVER_PORT envvironment variables")

    return (server_host, server_port, token)


class KlueMicroServiceTestCase(KlueTestCase):

    token = None

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        self.host, self.port, self.token = load_port_host_token()

    def assertIsVersion(self, j):
        self.assertTrue(type(j['version']) is str)
        self.assertTrue(type(j['name']) is str)
        self.assertTrue(type(j['container']) is str)

    def assertHasPing(self):
        self.assertGetReturnOk('ping')

    def assertHasVersion(self, verify_ssl=True):
        j = self.assertGetReturnJson('version', 200, verify_ssl=verify_ssl)
        self.assertIsVersion(j)

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
