import os
import sys
import yaml
import pprint
import logging


log = logging.getLogger(__name__)


class KlueConfig(object):

    def __init__(self, path=None):
        # Get the live host from klue-config.yaml
        paths = [
            os.path.join(os.path.dirname(sys.argv[0]), 'klue-config.yaml'),
            '/klue/klue-config.yaml',
            os.path.join(os.path.dirname(sys.argv[0]), 'test/klue-config.yaml'),
        ]

        if path:
            paths.append(path)

        config_path = None
        for p in paths:
            log.info("Looking for klue config at %s" % p)
            if os.path.isfile(p):
                config_path = p
                continue

        if not config_path:
            raise Exception("Failed to find klue-config.yaml!")

        with open(config_path, 'r') as stream:
            c = yaml.load(stream)
            for k, v in c.items():
                setattr(self, k, v)

        # Validate config
        if not hasattr(self, 'live_host'):
            raise Exception("'klue-config.yaml' lacks the 'live_host' key")


config = None

def get_config(path=None):
    global config
    if not config:
        config = KlueConfig(path=path)
        log.debug("Loaded configuration:\n%s" % pprint.pformat(vars(config), indent=4))
    return config
