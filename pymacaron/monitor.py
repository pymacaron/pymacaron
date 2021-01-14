from pymacaron.log import pymlogger
import os
from pymacaron.config import get_config
from pymacaron.utils import get_container_version


log = pymlogger(__name__)


# Which monitoring methods to use
use_scout = False


def monitor_init(app=None, config=None, celery=False):

    if not config:
        config = get_config()

    global use_scout

    # Note: at this point, pym_monitor should have been called earlier on to
    # start any eventual agent daemon required by the monitoring app.

    # Enable scoutapp monitoring
    if hasattr(config, 'scout_key'):
        use_scout = True
        appname = os.environ.get('PYM_ENV', 'dev')
        if hasattr(config, 'scout_app_name'):
            appname = config.scout_app_name
        scout_key = config.scout_key
        version = get_container_version()

        if celery:
            log.info("Setting up scoutapp monitoring for Celery jobs")
            import scout_apm.celery
            from scout_apm.api import Config

            Config.set(
                key=scout_key,
                name=appname,
                monitor=True,
                revision_sha=version,
            )

            scout_apm.celery.install()

        elif app:

            # Enable Flask monitoring for scoutapp
            log.info("Setting up scoutapp monitoring for Flask app")
            from scout_apm.flask import ScoutApm
            ScoutApm(app)
            app.config['SCOUT_KEY'] = scout_key
            app.config['SCOUT_NAME'] = appname
            app.config['SCOUT_MONITOR'] = True
            app.config['SCOUT_REVISION_SHA'] = version

    # END OF scoutapp support


class monitor():

    def __init__(self, kind='Unknown', method='Unknown'):
        self.kind = kind
        self.method = method

    def __enter__(self):
        global use_scout
        if use_scout:
            log.debug("START MONITOR %s/%s" % (self.kind, self.method))
            import scout_apm.api
            self.scout_decorator = scout_apm.api.instrument(self.method, tags={}, kind=self.kind)
            self.scout_decorator.__enter__()

    def __exit__(self, type, value, traceback):
        global use_scout
        if use_scout:
            log.debug("STOP MONITOR %s/%s" % (self.kind, self.method))
            self.scout_decorator.__exit__(type, value, traceback)
