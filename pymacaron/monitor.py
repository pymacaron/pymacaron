import logging
from pymacaron.config import get_config
from pymacaron.utils import get_app_name


log = logging.getLogger(__name__)


# Which monitoring methods to use
use_scout = False


def monitor_init(app, config=None):
    assert app
    if not config:
        config = get_config()

    global use_scout

    # Enable scoutapp monitoring
    if hasattr(config, 'scout_key'):
        use_scout = True
        appname = get_app_name()

        # Enable Flask monitoring for scoutapp
        from scout_apm.flask import ScoutApm
        ScoutApm(app)
        app.config['SCOUT_MONITOR'] = True
        app.config['SCOUT_KEY'] = config.scout_key
        app.config['SCOUT_NAME'] = appname

        # Enable custom instrumentation for scoutapp
        import scout_apm.api
        scout_apm.api.install(config={
            'name': appname,
            'key': config.scout_key,
            'monitor': True
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
