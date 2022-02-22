import re
from uuid import uuid4
from flask_cors import CORS
from flask import Response, redirect, abort
from pymacaron.config import get_config
from pymacaron.log import pymlogger


log = pymlogger(__name__)


def publish_api_specifications(app, path: str, api_paths: dict) -> None:
    """Add routes to the Flask app to publish all loaded swagger files under the
    paths doc/<api_name>.yaml and doc/<api_name>
    """

    # Allow cross-origin calls
    CORS(app, resources={r"/%s/*" % path: {"origins": "*"}})

    # Generate a list of yaml files edited to contain TOCs and proper
    # versioning
    yamls = {
        # api_name: yaml_string
    }

    fill_yamls(yamls, api_paths, path)

    def doc_endpoint(name=None):
        api_name = name.replace('.yaml', '')
        if api_name not in api_paths:
            log.info(f"Unknown api name '{api_name}'")
            abort(404)

        if name.endswith('.yaml'):
            # Show the swagger file
            return Response(yamls.get(api_name, ''), mimetype='text/plain')

        else:
            # Redirect to swagger-UI at petstore, to open this swagger file
            url = make_url(path, api_name)
            log.info(f"Redirecting to {url}")
            return redirect(url, code=302)

    path = path.strip('/')
    route = f'/{path}/<name>'
    log.info(f"Publishing apis under route {route}")
    app.add_url_rule(route, str(uuid4()), view_func=doc_endpoint, methods=['GET'])


def make_url(path, api_name):
    """Given the name of a swagger api, return a url to show it in a swagger UI"""
    conf = get_config()

    # Infer the live host url from pym-config.yaml
    proto = 'https'
    live_host = f"{proto}://{conf.live_host}"

    return f'http://petstore.swagger.io/?url={live_host}/{path}/{api_name}.yaml'


def fill_yamls(yamls: dict, api_paths: dict, path: str) -> dict:

    # Generate a table of content with all loaded apis

    toc = "    ## TOC\n"

    for api_name, api_path in api_paths:
        # TODO: order apis by decreasing number of endpoints
        with open(api_path, 'r') as f:
            title = None
            while not title:
                ln = f.readline()
                m = re.search(r'^\s*title:\s*(.+)', ln)
                if m:
                    title = m[1]

        url = make_url(path, api_name)
        toc += f"    - [{title}]({url})\n"

    # Now load all yamls, with TOCs
    for api_name, api_path in api_paths:
        with open(api_path, 'r') as f:
            spec = f.read()
            # TODO: insert TOC just after 'description: |'
            yamls[api_name] = spec
