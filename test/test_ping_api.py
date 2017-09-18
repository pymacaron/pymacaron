import os
import sys
import logging
import json
import imp
import pprint
import subprocess
from time import sleep
from klue_microservice.config import get_config
from klue_microservice.auth import generate_token, init_jwt_config


utils = imp.load_source('utils', os.path.join(os.path.dirname(__file__), 'utils.py'))


log = logging.getLogger(__name__)


class Tests(utils.KlueMicroServiceTests):

    def setUp(self):
        super().setUp()
        self.verify_ssl = False
        assert os.environ['KLUE_JWT_ISSUER']
        assert os.environ['KLUE_JWT_AUDIENCE']
        assert os.environ['KLUE_JWT_SECRET']
        self.kill_server()
        self.start_server()
        self.port = 8765

    def test_ping(self):
        self.assertHasPing()

    def test_version(self):
        self.assertHasVersion(verify_ssl=self.verify_ssl)

    def test_auth_version(self):
        # Generate a backend token
        root_dir = subprocess.Popen(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE).stdout.read()
        root_dir = root_dir.decode("utf-8").strip()

        # Load klue-config.yaml
        path = os.path.join(root_dir, 'test/klue-config.yaml')
        conf = get_config(path)
        init_jwt_config()
        conf.jwt_issuer = os.environ['KLUE_JWT_ISSUER']
        conf.jwt_secret = os.environ['KLUE_JWT_SECRET']
        conf.jwt_audience = os.environ['KLUE_JWT_AUDIENCE']

        log.debug("Config is:\n%s" % pprint.pformat(vars(get_config()), indent=4))

        self.token = generate_token(user_id='killroy was here')

        self.assertHasAuthVersion(verify_ssl=self.verify_ssl)
