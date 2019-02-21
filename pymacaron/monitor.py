import logging
from pymacaron.config import get_config
from pymacaron.utils import get_app_name


log = logging.getLogger(__name__)


# Which monitoring methods to use
use_scout = False


def monitor_init(app=None, config=None, celery=False):

    if not config:
        config = get_config()

    global use_scout

    # Enable scoutapp monitoring
    if hasattr(config, 'scout_key'):
        use_scout = True
        appname = get_app_name()
        scout_key = config.scout_key
        scout_core_dir = config.scout_core_agent_dir if hasattr(config, 'scout_core_agent_dir') else '/tmp/scout_apm_core'

        if celery:
            import scout_apm.celery
            from scout_apm.api import Config

            Config.set(
                key=scout_key,
                name=appname,
                monitor=True,
                core_agent_dir=scout_core_dir,
            )

            scout_apm.celery.install()

        elif app:

            # Enable Flask monitoring for scoutapp
            from scout_apm.flask import ScoutApm
            ScoutApm(app)
            app.config['SCOUT_MONITOR'] = True
            app.config['SCOUT_KEY'] = scout_key
            app.config['SCOUT_NAME'] = appname
            app.config['SCOUT_CORE_AGENT_DIR'] = scout_core_dir

            # Enable custom instrumentation for scoutapp
            import scout_apm.api
            scout_apm.api.install(config={
                'name': 'FOOBAR',
                'key': scout_key,
                'monitor': True,
                'core_agent_dir': scout_core_dir,
            })

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
