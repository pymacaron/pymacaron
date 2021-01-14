import os
from pymacaron.log import pymlogger
import imp
import pprint
import subprocess
from pymacaron.config import get_config
from pymacaron.auth import generate_token


utils = imp.load_source('utils', os.path.join(os.path.dirname(__file__), 'utils.py'))


log = pymlogger(__name__)


class Tests(utils.PyMacaronTests):

    def setUp(self):
        super().setUp()
        self.verify_ssl = False
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

        # Load pym-config.yaml
        path = os.path.join(root_dir, 'test/pym-config.yaml')
        get_config(path)
        log.debug("Config is:\n%s" % pprint.pformat(vars(get_config()), indent=4))

        self.token = generate_token(user_id='killroy was here')

        self.assertHasAuthVersion(verify_ssl=self.verify_ssl)
