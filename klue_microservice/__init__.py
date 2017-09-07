import os
import sys
import logging
from flask_compress import Compress
from klue.swagger.apipool import ApiPool
from klue_microservice.log import set_level
from klue_microservice.api import do_ping
from klue_microservice.crash import set_error_reporter, crash_handler
from klue_microservice.exceptions import format_error


log = logging.getLogger(__name__)


#
# API: class to define then run a micro service api
#

class API(object):


    def __init__(self, app, host='localhost', port=80, debug=False, log_level=logging.DEBUG, formats=None, timeout=20, error_reporter=None):
        """Take the flask app, and optionally the http port to listen on, and
        whether flask's debug mode is one or not, which callback to call when
        catching exceptions, and the api's log level"""
        assert app
        self.app = app
        self.port = port
        self.host = host
        self.debug = debug
        self.formats = formats
        self.timeout = timeout
        set_level(log_level)
        if error_reporter:
            set_error_reporter(error_reporter)
        log.info("Initialized API (%s:%s) (Flask debug:%s)" % (host, port, debug))


    def load_apis(self, path):
        """Load all swagger files found at the given path"""

        if not path:
            raise Exception("Missing path to api swagger files")

        # Find all swagger apis under 'path'
        apis = {}

        log.debug("Searching path %s" % path)
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.endswith('.yaml'):
                    api_name = f.replace('.yaml', '')
                    apis[api_name] = os.path.join(path, f)
                    log.debug("Found api %s in %s" % (api_name, f))

        self.path_apis = path
        self.apis = apis


    def start(self, debug=False, serve=[]):
        """Start the API server"""

        # Check arguments
        if type(serve) is str:
            serve = [serve]
        elif type(serve) is list:
            pass
        else:
            raise Exception("'serve' should be an api name or a list of api names")

        if len(serve) == 0:
            raise Exception("You must specify at least one api to serve")

        for api_name in serve:
            if api_name not in self.apis:
                raise Exception("Can't find %s.yaml (swagger file) in the api directory %s" % (api_name, self.path_apis))

        app = self.app
        app.secret_key = os.urandom(24)

        # Let's compress returned data when possible
        compress = Compress()
        compress.init_app(app)

        # All apis that are not served locally are not persistent
        not_persistent = []
        for api_name in self.apis.keys():
            if api_name in serve:
                pass
            else:
                not_persistent.append(api_name)

        # Now load those apis into the ApiPool
        for api_name, api_path in self.apis.items():

            host = None
            port = None

            if api_name in serve:
                # We are serving this api locally: override the host:port specified in the swagger spec
                host = self.host
                port = self.port

            do_persist = True if api_name not in not_persistent else False
            local = True if api_name in serve else False

            log.info("Loading api %s from %s (persist: %s)" % (api_name, api_path, do_persist))
            ApiPool.add(
                api_name,
                yaml_path=api_path,
                timeout=self.timeout,
                error_callback=format_error,
                formats=self.formats,
                do_persist=do_persist,
                host=host,
                port=port,
                local=local,
            )

        ApiPool.merge()

        # Add default healthcheck routes
        app.add_url_rule('/ping', 'do_ping', do_ping)

        # Now spawn flask routes for all endpoints
        for api_name in self.apis.keys():
            log.info("Spawning api %s" % api_name)
            api = getattr(ApiPool, api_name)
            api.spawn_api(app, decorator=crash_handler)

        if os.path.basename(sys.argv[0]) == 'gunicorn':
            # Gunicorn takes care of spawning workers
            return

        # Debug mode is the default when not running via gunicorn
        app.debug = debug
        app.run(host='0.0.0.0', port=port)
