import os
import sys
import logging
import click
import pkg_resources
import inspect
from uuid import uuid4
from flask import Response, redirect
from flask_compress import Compress
from flask_cors import CORS
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron_core.models import get_model
import pymacaron.models
from pymacaron.log import set_level, pymlogger
from pymacaron.crash import set_error_reporter, generate_crash_handler_decorator
from pymacaron.exceptions import format_error
from pymacaron.config import get_config
from pymacaron.monitor import monitor_init
from pymacaron.api import add_ping_hook


log = pymlogger(__name__)


def _get_model_factory(model_name):
    # Using dynamic method creation to localize model_name
    def factory(**kwargs):
        return get_model(model_name)(**kwargs)
    return factory


def get_port():
    """Find which TCP port to listen to, based on environment variables"""
    if 'PORT' in os.environ:
        port = os.environ['PORT']
        log.info("Environment variable PORT is set: will listen on port %s" % port)
    elif 'PYM_SERVER_PORT' in os.environ:
        port = os.environ['PYM_SERVER_PORT']
        log.info("Environment variable PYM_SERVER_PORT is set: will listen on port %s" % port)
    else:
        port = 80
        log.info("No HTTP port specified. Will listen on port 80")

    return port


#
# API: class to define then run a micro service api
#

class API(object):


    def __init__(self, app, host='localhost', port=None, debug=False, log_level=logging.DEBUG, formats=None, timeout=20, error_reporter=None, default_user_id=None, error_callback=format_error, error_decorator=None, ping_hook=[]):
        """

        Configure the Pymacaron microservice prior to starting it. Arguments:

        - app: the flask app
        - port: (optional) the http port to listen on (defaults to 80)
        - debug: (optional) whether to run with flask's debug mode (defaults to False)
        - error_reporter: (optional) a callback to call when catching exceptions, for custom reporting to slack, email or whatever
        - log_level: (optional) the microservice's log level (defaults to logging.DEBUG)
        - ping_hook: (optional) a function to call each time Amazon calls the ping endpoint, which happens every few seconds

        """
        assert app
        assert port

        self.app = app
        self.port = port
        self.host = host
        self.debug = debug
        self.formats = formats
        self.timeout = timeout
        self.error_callback = error_callback
        self.error_decorator = error_decorator
        self.ping_hook = ping_hook

        if not port:
            self.port = get_port()

        if default_user_id:
            self.default_user_id = default_user_id

        set_level(log_level)

        if error_reporter:
            set_error_reporter(error_reporter)

        log.info("Initialized API (%s:%s) (Flask debug:%s)" % (host, port, debug))


    def _load_model_aliases(self, api):
        """Load all PyMacaronModels generated for a given api into the namespace
        of pymacaron.models so a user may write 'from pymacaron.models import <SomeModel>'
        """

        for model_name in dir(api.model):
            model_class = getattr(api.model, model_name)
            if inspect.isclass(model_class) and 'to_json' in dir(model_class):
                setattr(pymacaron.models, model_name, _get_model_factory(model_name))


    def load_clients(self, path=None, apis=[]):
        """Generate client libraries for the given apis, without starting an
        api server"""

        if not path:
            raise Exception("Missing path to api swagger files")

        if type(apis) is not list:
            raise Exception("'apis' should be a list of api names")

        if len(apis) == 0:
            raise Exception("'apis' is an empty list - Expected at least one api name")

        for api_name in apis:
            api_path = os.path.join(path, '%s.yaml' % api_name)
            if not os.path.isfile(api_path):
                raise Exception("Cannot find swagger specification at %s" % api_path)
            log.info("Loading api %s from %s" % (api_name, api_path))
            api = ApiPool.add(
                api_name,
                yaml_path=api_path,
                timeout=self.timeout,
                error_callback=self.error_callback,
                formats=self.formats,
                do_persist=False,
                local=False,
            )
            self._load_model_aliases(api)

        return self


    def load_apis(self, path, ignore=[], include_crash_api=False):
        """Load all swagger files found at the given path, except those whose
        names are in the 'ignore' list"""

        if not path:
            raise Exception("Missing path to api swagger files")

        if type(ignore) is not list:
            raise Exception("'ignore' should be a list of api names")

        # Always ignore pym-config.yaml
        ignore.append('pym-config')

        # Find all swagger apis under 'path'
        apis = {}

        log.debug("Searching path %s" % path)
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.endswith('.yaml'):
                    api_name = f.replace('.yaml', '')

                    if api_name in ignore:
                        log.info("Ignoring api %s" % api_name)
                        continue

                    apis[api_name] = os.path.join(path, f)
                    log.debug("Found api %s in %s" % (api_name, f))

        # And add pymacaron's default ping and crash apis
        for name in ['ping', 'crash']:
            yaml_path = pkg_resources.resource_filename(__name__, 'pymacaron/%s.yaml' % name)
            if not os.path.isfile(yaml_path):
                yaml_path = os.path.join(os.path.dirname(sys.modules[__name__].__file__), '%s.yaml' % name)
            apis[name] = yaml_path

        if not include_crash_api:
            del apis['crash']

        # Save found apis
        self.path_apis = path
        self.apis = apis

        return self


    def publish_apis(self, path='doc'):
        """Publish all loaded apis on under the uri /<path>/<api-name>, by
        redirecting to http://petstore.swagger.io/
        """

        assert path

        if not self.apis:
            raise Exception("You must call .load_apis() before .publish_apis()")

        # Infer the live host url from pym-config.yaml
        proto = 'http'
        if hasattr(get_config(), 'aws_cert_arn'):
            proto = 'https'

        live_host = "%s://%s" % (proto, get_config().live_host)

        # Allow cross-origin calls
        CORS(self.app, resources={r"/%s/*" % path: {"origins": "*"}})

        # Add routes to serve api specs and redirect to petstore ui for each one
        for api_name, api_path in self.apis.items():

            api_filename = os.path.basename(api_path)
            log.info("Publishing api %s at /%s/%s" % (api_name, path, api_name))

            def redirect_to_petstore(live_host, api_filename):
                def f():
                    url = 'http://petstore.swagger.io/?url=%s/%s/%s' % (live_host, path, api_filename)
                    log.info("Redirecting to %s" % url)
                    return redirect(url, code=302)
                return f

            def serve_api_spec(api_path):
                def f():
                    with open(api_path, 'r') as f:
                        spec = f.read()
                        log.info("Serving %s" % api_path)
                        return Response(spec, mimetype='text/plain')
                return f

            self.app.add_url_rule('/%s/%s' % (path, api_name), str(uuid4()), redirect_to_petstore(live_host, api_filename))
            self.app.add_url_rule('/%s/%s' % (path, api_filename), str(uuid4()), serve_api_spec(api_path))

        return self


    def start(self, serve=[]):
        """Load all apis, either as local apis served by the flask app, or as
        remote apis to be called from whithin the app's endpoints, then start
        the app server"""

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

        # Initialize JWT config
        conf = get_config()
        if hasattr(conf, 'jwt_secret'):
            log.info("Set JWT parameters to issuer=%s audience=%s secret=%s***" % (
                conf.jwt_issuer,
                conf.jwt_audience,
                conf.jwt_secret[0:8],
            ))

        # Always serve the ping api
        serve.append('ping')

        # Add ping hooks if any
        if self.ping_hook:
            add_ping_hook(self.ping_hook)

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
            api = ApiPool.add(
                api_name,
                yaml_path=api_path,
                timeout=self.timeout,
                error_callback=self.error_callback,
                formats=self.formats,
                do_persist=do_persist,
                host=host,
                port=port,
                local=local,
            )

            self._load_model_aliases(api)

        # Make sure schema objects from different APIs don't conflict with each other
        ApiPool.merge()

        # Now spawn flask routes for all endpoints
        for api_name in self.apis.keys():
            if api_name in serve:
                log.info("Spawning api %s" % api_name)
                api = getattr(ApiPool, api_name)
                # Spawn api and wrap every endpoint in a crash handler that
                # catches replies and reports errors
                api.spawn_api(app, decorator=generate_crash_handler_decorator(self.error_decorator))

        log.debug("Argv is [%s]" % '  '.join(sys.argv))
        if 'celery' in sys.argv[0].lower():
            # This code is loading in a celery worker - Don't start the actual flask app.
            log.info("Running in a Celery worker - Not starting the Flask app")
            return

        # Initialize monitoring, if any is defined
        monitor_init(app=app, config=conf)

        if os.path.basename(sys.argv[0]) == 'gunicorn':
            # Gunicorn takes care of spawning workers
            log.info("Running in Gunicorn - Not starting the Flask app")
            return

        # Debug mode is the default when not running via gunicorn
        app.debug = self.debug

        app.run(host='0.0.0.0', port=self.port)

#
# Generic code to start server, from command line or via gunicorn
#


def show_splash():
    log.info("")
    log.info("")
    log.info("")
    log.info("       _ __  _   _ _ __ ___   __ _  ___ __ _ _ __ ___  _ __ ")
    log.info("      | '_ \| | | | '_ ` _ \ / _` |/ __/ _` | '__/ _ \| '_ \ ")
    log.info("      | |_) | |_| | | | | | | (_| | (_| (_| | | | (_) | | | |")
    log.info("      | .__/ \__, |_| |_| |_|\__,_|\___\__,_|_|  \___/|_| |_|")
    log.info("      | |     __/ |")
    log.info("      |_|    |___/")
    log.info("")
    log.info("       microservices made easy    -     http://pymacaron.com")
    log.info("")
    log.info("")
    log.info("")


def letsgo(name, callback=None):
    assert callback

    @click.command()
    @click.option('--port', help="Set server listening port (default: 80)", default=None)
    @click.option('--env', help="Set the environment, hence forcing to run against live, staging or dev by setting the PYM_ENV variable", default=None)
    @click.option('--debug/--no-debug', default=True)
    def main(port, env, debug):

        if env:
            log.info("Overriding PYM_ENV to '%s'" % env)
            os.environ['PYM_ENV'] = env

        conf = get_config()

        show_splash()
        if not port:
            port = get_port()

        # Start celeryd and redis?
        if hasattr(conf, 'with_async') and conf.with_async:
            from pymacaron_async import start_celery
            start_celery(port, debug)

        # Proceed to start the API server
        callback(port, debug)

    if name == "__main__":
        main()

    if os.path.basename(sys.argv[0]) == 'gunicorn':
        show_splash()
        port = get_port()
        callback(port)
