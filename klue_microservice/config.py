import os
import sys
import yaml
import pprint
import logging
from copy import deepcopy


log = logging.getLogger(__name__)


class KlueConfig(object):

    def __init__(self, path=None):

        # Some defaults, required by klue_microservice.auth
        self.jwt_issuer = None
        self.jwt_audience = None
        self.jwt_secret = None
        self.jwt_token_timeout = 86400
        self.jwt_token_renew_after = 10800
        self.default_user_id = 'KLUE_DEFAULT_USER_ID'

        # Default time-limit for the slow-call report
        self.report_call_exceeding_ms = 1000

        # Get the live host from klue-config.yaml
        paths = [
            os.path.join(os.path.dirname(sys.argv[0]), 'klue-config.yaml'),
            '/klue/klue-config.yaml',
            os.path.join(os.path.dirname(sys.argv[0]), 'test/klue-config.yaml'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'klue-config.yaml')
        ]

        if path:
            paths.append(path)

        config_path = None
        for p in paths:
            p = os.path.abspath(p)
            log.info("Looking for klue config at %s" % p)
            if os.path.isfile(p):
                config_path = p
                continue

        if not config_path:
            raise Exception("Failed to find klue-config.yaml!")

        self.config_path = config_path

        log.info("Loading config file at %s" % config_path)
        all_keys = []
        config_dict = {}
        with open(config_path, 'r') as stream:
            config_dict = yaml.load(stream)
            for k, v in config_dict.items():
                setattr(self, k, v)
                all_keys.append(k)

        # Validate config
        if not hasattr(self, 'live_host'):
            raise Exception("'klue-config.yaml' lacks the 'live_host' key")

        # Magic here :-)
        # For all keys whose value is in the list of enironment secrets, replace
        # that value with the value of the corresponding environment variable.
        if hasattr(self, 'env_secrets'):
            log.info("Substituting secret environment variable names for their values in config")
            for k in all_keys:
                if getattr(self, k) in self.env_secrets:
                    setattr(self, k, os.environ.get(getattr(self, k), k))
                    config_dict[k] = str(getattr(self, k))[0:8] + '****'

        # Print config file to log, but obfuscate secrets
        log.debug("Loaded configuration:\n%s" % pprint.pformat(config_dict, indent=4))


config = None

def get_config(path=None):
    global config
    if not config:
        config = KlueConfig(path=path)
    return config
