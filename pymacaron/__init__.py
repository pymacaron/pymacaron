import os
import sys
import logging
import click
import pkg_resources
from datetime import datetime
from uuid import uuid4
from flask import Response, redirect, abort
from flask_compress import Compress
from flask_cors import CORS
from pymacaron.apiloader import load_api_models_and_endpoints
from pymacaron.log import set_level, pymlogger
from pymacaron.config import get_config
from pymacaron.monitor import monitor_init
from pymacaron.crash import set_error_reporter
from pymacaron.api import add_ping_hook


log = pymlogger(__name__)


class modelpool():
    """The modelpool of an api is a class whose attributes are all the Pymacaron
    model classes declared in that api
    """

    def __init__(self, name):
        self.api_name = name
        self._model_names = []

    def get_model_names(self):
        return self._model_names

    def add_model(self, model_name, model_class):
        self._model_names.append(model_name)
        setattr(self, model_name, model_class)

    def __getattr__(self, model_name):
        raise Exception(f'Either {self.api_name}.yaml has not been loaded or it does not define object {model_name}')

    def json_to_model(self, model_name, j, keep_datetime=None, prune_none=True):
        """Given a model name and json dict, return an instantiated pymacaron object"""
        # TODO: keep_datetime in this method should be deprecated...
        assert keep_datetime is not False, "Support for keep_datetime=False not implemented"
        return getattr(self, model_name).from_json(j, prune_none=prune_none)


class apipool():
    """The apipool contains the modelpools of all loaded apis"""

    # api_name: api_path
    __api_paths = {}

    @classmethod
    def add_model(cls, api_name, model_name, model_class):
        """Register a model class defined in an api"""
        # Set modelpool.<model_name> to model_class. This allows writing:
        #   from pymacaron import apipool
        #   o = apipool.ping.Ok()
        if not hasattr(apipool, api_name):
            setattr(apipool, api_name, modelpool(api_name))
        models = getattr(apipool, api_name)
        models.add_model(model_name, model_class)

    @classmethod
    def get_model(cls, api_name):
        """Return the pymacaron modelpool for this api"""
        assert hasattr(apipool, api_name), f"Api {api_name} is not loaded in apipool"
        return getattr(apipool, api_name)

    @classmethod
    def get_api_names(cls):
        """Return the names of loaded apis"""
        return sorted(apipool.__api_paths.keys())

    @classmethod
    def load_swagger(cls, api_name, api_path, dest_dir=None, create_endpoints=False, force=False, model_file=None, app_file=None):
        """Load a swagger/openapi specification into pymacaron: generate its model
        classes (declared with pydantic), and optionally generate the Flask api
        endpoints binding endpoint methods to routes.

        Syntax:
            apipool.load_swagger('ping', '../apis/ping.yaml')

        api_name : str
            Name of the api, used to access api models.
        api_path : str
            Path of the swagger file of the api.
        dest_dir: str
            Optional. Path to a directory under which to write the generated
            '<api_name>_models.py' and '<api_name>_app.py' files. Defaults to
            the same directory as the swagger file.
        create_endpoints: bool
            Optional. Set to false to only generate model declarations, and not
            endpoint declarations. Defaults to true.
        force: bool
            Optional. Force regenerating the model and endpoint code even if
            the code files are up to date with the swagger file. Defaults to
            false.

        """

        app_pkg = load_api_models_and_endpoints(
            api_name=api_name,
            api_path=api_path,
            dest_dir=dest_dir,
            create_endpoints=create_endpoints,
            force=force,
            model_file=model_file,
            app_file=app_file,
        )

        # Remember where this api's swagger is located
        apipool.__api_paths[api_name] = api_path

        return app_pkg

    @classmethod
    def enforce_global_model_names(cls):
        """Find all models that have the same names in different apis and compare their
        schema declarations.  Raise an error if at least two of them differ,
        and show all the differences that were found as a diff of their json
        schemas.
        """

        model_name_to_apis = {}

        for api_name in apipool.__api_paths.keys():
            api = getattr(apipool, api_name)
            for model_name in api.get_model_names():
                if model_name not in model_name_to_apis:
                    model_name_to_apis[model_name] = []
                model_name_to_apis[model_name].append(api)

        found_names = []

        for model_name in sorted(model_name_to_apis.keys()):
            apis = model_name_to_apis[model_name]
            cnt = len(apis)
            if cnt > 1:
                log.info(f"Found {model_name} in {cnt} apis: {', '.join([str(a) for a in apis])}")
                m0 = getattr(apis[0], model_name)
                for api in apis[1:]:
                    m1 = getattr(api, model_name)
                    diff = m0.diff_with(m1)
                    if diff:
                        log.error('\n' + diff)
                        if model_name not in found_names:
                            found_names.append(model_name)

        if found_names:
            raise Exception(f"Found models with same names but different schemas in different apis: {', '.join(found_names)}")

    @classmethod
    def publish_apis(cls, app, path='doc', toc=None):
        """Add routes to the Flask app to publish all loaded swagger files under the
        paths doc/<api_name>.yaml and doc/<api_name>. Optionally add a table of
        content to all swagger specs.

        """

        if not apipool.__api_paths:
            raise Exception("You must call .load_apis() before .publish_apis()")

        conf = get_config()

        # Infer the live host url from pym-config.yaml
        proto = 'https'
        live_host = f"{proto}://{conf.live_host}"

        # Allow cross-origin calls
        CORS(app, resources={r"/%s/*" % path: {"origins": "*"}})

        def doc_endpoint(name=None):
            api_name = name.replace('.yaml', '')
            if api_name not in apipool.__api_paths:
                log.info(f"Unknown api name '{api_name}'")
                abort(404)

            api_path = apipool.__api_paths[api_name]

            if name.endswith('.yaml'):
                # Show the swagger file
                with open(api_path, 'r') as f:
                    spec = f.read()

                    if toc:
                        # Insert the table of content after the first 'description: |'
                        spec.replace('description: |', f'description: |\n{toc}\n', 1)

                    toc.info("Returning %s" % api_path)
                    return Response(spec, mimetype='text/plain')

            else:
                # Redirect to swagger-UI at petstore, to open this swagger file
                url = f'http://petstore.swagger.io/?url={live_host}/{path}/{api_name}.yaml'
                log.info(f"Redirecting to {url}")
                return redirect(url, code=302)

        path = path.strip('/')
        route = f'/{path}/<name>'
        log.info(f"Publishing apis under route {route}")
        app.add_url_rule(route, str(uuid4()), view_func=doc_endpoint, methods=['GET'])


class jsonencoders:

    # Default encoder when serializing datetime to Flask response
    __json_encoders = {
        datetime: lambda d: d.isoformat(),
    }

    @classmethod
    def set_json_encoders(cls, encoders):
        assert type(encoders) is dict, "json_encoders must be a dict of type/callable"
        assert datetime in encoders, "json_encoders must define an encoder for datetime"
        assert callable(encoders[datetime]), "json_encoders[datetime] must be a callable"
        cls.__json_encoders = encoders


    @classmethod
    def get_datetime_encoder(cls):
        assert datetime in jsonencoders.__json_encoders
        return jsonencoders.__json_encoders[datetime]


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


    def __init__(self, app, host='localhost', port=None, debug=False, log_level=logging.DEBUG, json_encoders=None, error_reporter=None, error_callback=None, default_user_id=None, ping_hook=[]):
        """

        Configure the Pymacaron microservice prior to starting it. Arguments:

        app : the flask app

        port : (optional) the http port to listen on (defaults to 80)

        debug : (optional) whether to run with flask's debug mode (defaults to False)

        error_callback : (optional) takes the exception caught while executing an endpoint and return its json representation in the microservice's own error format

        error_reporter : (optional) takes the exception caught in an endpoint together with a title and long text trace, and reports them wherever is relevant

        log_level : (optional) the microservice's log level (defaults to logging.DEBUG)

        ping_hook : (optional) a function to call each time Amazon calls the ping endpoint, which happens every few seconds

        json_encoders: (optional) custom pydantic json encoders, to use when serializing pymacaron models to json

        """
        assert app
        assert port

        self.app = app
        self.port = port
        self.host = host
        self.debug = debug
        self.error_callback = error_callback
        self.error_reporter = error_reporter
        self.ping_hook = ping_hook
        self.app_pkgs = []

        if not port:
            self.port = get_port()

        if default_user_id:
            self.default_user_id = default_user_id

        set_level(log_level)

        if json_encoders:
            log.info(f"Using custom json encoder when serializing Flask response: {json_encoders}")
            jsonencoders.set_json_encoders(json_encoders)

        log.info("Initialized API (%s:%s) (Flask debug:%s)" % (host, port, debug))


    def publish_apis(self, path='doc', toc=None):
        """Publish all loaded apis on under the uri /<path>/<api-name>, by redirecting
        to http://petstore.swagger.io/. Optionally add a common table of
        content (provided in markdown) to all apis' yaml files.
        """
        apipool.publish_apis(self.app, path=path, toc=toc)


    def load_builtin_apis(self, names=['ping']):
        """Load some or all of the builtin apis 'ping' and 'crash'"""
        for name in names:
            yaml_path = pkg_resources.resource_filename(__name__, 'pymacaron/%s.yaml' % name)
            if not os.path.isfile(yaml_path):
                yaml_path = os.path.join(os.path.dirname(sys.modules[__name__].__file__), '%s.yaml' % name)
            app_pkg = apipool.load_swagger(
                name,
                yaml_path,
                dest_dir=get_config().apis_path,
                create_endpoints=True,
            )
            if app_pkg:
                self.app_pkgs.append(app_pkg)


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
            apipool.load_swagger(
                api_name,
                api_path,
                dest_dir=path,
                create_endpoints=False,
            )

        return self


    def load_apis(self, path=None, ignore=[], only_models=[], force=False, global_names=False):
        """Find all swagger files under the given path. Ignore those whose name is in
        the ignore list. Generate and load models for all others. Generate
        Flask app code for all except those in ignore and only_models list.

        If global_names is true, load_apis() will check all generated models
        from all loaded apis and if two models with the same name but different
        schemas are found, raise an exception and show the diff between those
        two models.

        """

        if not path:
            path = get_config().apis_path

        if type(ignore) is not list:
            raise Exception("'ignore' should be a list of api names")

        if type(only_models) is not list:
            raise Exception("'ignore' should be a list of api names")

        # Always ignore pym-config.yaml
        ignore.append('pym-config')

        # Find all swagger apis under 'path'
        apis = {}

        log.debug("Searching swagger files under path %s" % path)
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.startswith('.#') or f.startswith('#'):
                    log.info("Ignoring file %s" % f)
                elif f.endswith('.yaml'):
                    api_name = f.replace('.yaml', '')

                    if api_name in ignore:
                        log.info("Ignoring api %s" % api_name)
                        continue

                    apis[api_name] = os.path.join(path, f)
                    log.debug("Found api %s in %s" % (api_name, f))

        # Now generate the model and app code for all these files
        for api_name, api_path in apis.items():
            app_pkg = apipool.load_swagger(
                api_name,
                api_path,
                dest_dir=os.path.dirname(api_path),
                create_endpoints=False if api_name in only_models else True,
                force=force,
                # TODO: custom formats
                # formats=self.formats,
            )
            if app_pkg:
                self.app_pkgs.append(app_pkg)

        if global_names:
            apipool.enforce_global_model_names()

        return self


    def start(self):
        """Load all apis, either as local apis served by the flask app, or as
        remote apis to be called from whithin the app's endpoints, then start
        the app server"""

        self.app.secret_key = os.urandom(24)

        set_error_reporter(self.error_reporter)

        # Initialize JWT config
        conf = get_config()
        if hasattr(conf, 'jwt_secret'):
            log.info("Set JWT parameters to issuer=%s audience=%s secret=%s***" % (
                conf.jwt_issuer,
                conf.jwt_audience,
                conf.jwt_secret[0:8],
            ))

        # Add ping hooks if any
        if self.ping_hook:
            add_ping_hook(self.ping_hook)

        self.load_builtin_apis()

        # Let's compress returned data when possible
        compress = Compress()
        compress.init_app(self.app)

        # Now execute Flask code declaring API routes
        for app_pkg in self.app_pkgs:
            app_pkg.load_endpoints(
                app=self.app,
                error_callback=self.error_callback,
                # formats=self.formats,
                # local=False,
            )

        log.debug("Argv is [%s]" % '  '.join(sys.argv))
        if 'celery' in sys.argv[0].lower():
            # This code is loading in a celery worker - Don't start the actual flask app.
            log.info("Running in a Celery worker - Not starting the Flask app")
            return

        # Initialize monitoring, if any is defined
        monitor_init(app=self.app, config=conf)

        if os.path.basename(sys.argv[0]) == 'gunicorn':
            # Gunicorn takes care of spawning workers
            log.info("Running in Gunicorn - Not starting the Flask app")
            return

        # Debug mode is the default when not running via gunicorn
        self.app.debug = self.debug

        self.app.run(host='0.0.0.0', port=self.port)

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
