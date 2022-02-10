import os
import re
import yaml
import importlib.util
from pymacaron.log import pymlogger


log = pymlogger(__name__)


def modified_time(path):
    return os.path.getmtime(path)


def swagger_type_to_pydantic_type(t, models=[]):
    """Given a swagger type or format or ref definition, return its corresponding python type"""
    # Take a swagger type and return the corresponding python type
    if t in models:
        return t

    mapping = {
        # swagger type: pydantic type (https://pydantic-docs.helpmanual.io/usage/types)
        'boolean': 'bool',
        'int32': 'int',
        'integer': 'int',
        'string': 'str',
        'number': 'float',
        'date': 'datetime',
        'datetime': 'datetime',
        'date-time': 'datetime',
        'iso-date': 'datetime',
    }

    assert t in mapping, f"Don't know to map swagger type '{t}' to a python type"

    return mapping[t]


def ref_to_model_name(s):
    """Take the '#/definitions/...' string in a $ref: statement, and return the name of the model referenced"""
    return s.split('/')[-1].replace("'", "").replace('"', '').strip()


def generate_models_v2(swagger, model_file, api_name):
    """Extract all model definitions from this swagger file and write a python
    module defining every corresponding pymacaron model class
    """

    log.info(f"Regenerating {model_file}")

    # List all model names in definitions
    all_models = list(swagger['definitions'].keys())
    all_models.sort()
    str_all_models = ', '.join([f'"{s}"' for s in all_models])

    def def_to_type(prop_def, model_name, prop_name):
        """Figure out the python type of a property"""
        assert type(prop_def) is dict, f"Expected a dict instead of '{prop_def}' in definition of {model_name}:{prop_name}"
        t = None
        if '$ref' in prop_def:
            s = prop_def['$ref']
            assert s.startswith("#/definitions/"), f"Failed to parse ref '{s}' in definition of {model_name}:{prop_name}"
            t = ref_to_model_name(s)
        elif 'enum' in prop_def:
            assert type(prop_def['enum']) is list
            str_enum = ', '.join(f'"{s}"' for s in prop_def['enum'])
            t = f'Literal[None, {str_enum}]'
            return t
        elif 'format' in prop_def:
            t = prop_def['format']
        elif 'type' in prop_def:
            t = prop_def['type']
        else:
            raise Exception(f"Don't know how to identify type in '{prop_def}' definition of {model_name}:{prop_name}")

        if t in all_models:
            return t

        return swagger_type_to_pydantic_type(t, all_models)

    def get_parent(model_def):
        """Return (parent_module_path, parent_class) or None for this model definition"""
        parent = model_def.get('x-parent', None)
        if parent:
            cls = parent.split('.')[-1]
            path = '.'.join(parent.split('.')[0:-1])
            return (path, cls)
        return (None, None)

    def def_to_model_dependencies(model_def, model_name):
        """Given a model definition, return all the model it references to"""
        deps = []
        assert 'properties' in model_def, f"No 'properties' defined for model '{model_name}'"
        for prop_name, prop_def in model_def['properties'].items():
            if prop_def.get('type', '').lower() == 'array':
                assert 'items' in prop_def, f"Expected 'items' in array definition of {model_name}:{prop_name}"
                t = def_to_type(prop_def['items'], model_name, prop_name)
            else:
                t = def_to_type(prop_def, model_name, prop_name)
            if t in all_models:
                deps.append(t)
        return deps

    # List all the parent classe we need to import before declaring models
    imports = []
    for model_name, model_def in swagger['definitions'].items():
        (path, cls) = get_parent(model_def)
        if path and cls:
            imports.append(f'from {path} import {cls} as Parent{cls}')

    # Code lines of the python file
    lines = [
        '# This is an auto-generated file - DO NOT EDIT!!!',
        'from pymacaron.model import PymacaronBaseModel',
        'from pydantic import BaseModel',
        'from typing import List, Optional, Literal',
        'from datetime import datetime',
    ] + imports + [
        '',
        f'__all_models = [{str_all_models}]',
        '',
    ]

    # Now comes a tricky part: we need to sort class declarations so that
    # classes are declared before they are referenced in the type constraints
    # of other classes.

    ordered_names = []
    deps_by_name = {}
    for model_name, model_def in swagger['definitions'].items():
        deps_by_name[model_name] = def_to_model_dependencies(model_def, model_name)

    while len(deps_by_name):
        for name in list(deps_by_name.keys()):
            all_declared = True
            for dep in deps_by_name[name]:
                if dep not in ordered_names:
                    all_declared = False
            if all_declared:
                ordered_names.append(name)
                del deps_by_name[name]

    # Now let's declare every class, in the right order
    for model_name in ordered_names:
        model_def = swagger['definitions'][model_name]

        str_properties = ', '.join([f'"{s}"' for s in list(model_def['properties'].keys())])

        str_nullable_properties = ', '.join([f'"{s}"' for s, d in model_def['properties'].items() if d.get('x-nullable', False) is True])

        (path, cls) = get_parent(model_def)
        x_parent = f'Parent{cls}, ' if cls else ''

        lines += [
            '',
            '',
            f'class {model_name}({x_parent}PymacaronBaseModel, BaseModel):',
            '    def get_property_names(self):',
            f'        return [{str_properties}]',
            '    def get_model_api(self):',
            f'        return "{api_name}"',
            '    def get_nullable_properties(self):',
            f'        return [{str_nullable_properties}]',
        ]

        for p_name, p_def in model_def['properties'].items():

            p_type = ''
            if p_def.get('type', '').lower() == 'array':
                assert 'items' in p_def, f"Expected 'items' in array definition of {model_name}:{p_name}"
                t = def_to_type(p_def['items'], model_name, p_name)
                p_type = f'List[{t}]'
            else:
                t = def_to_type(p_def, model_name, p_name)
                p_type = t

            # By default, pydantic attributes are optional. But if the property
            # has 'x-mandatory: true', then it becomes required.
            if p_def.get('x-mandatory', False) is True:
                lines.append(f'    {p_name}: {p_type}')
            else:
                lines.append(f'    {p_name}: Optional[{p_type}] = None')

    lines.append('')
    lines.append('')

    with open(model_file, 'w') as f:
        f.write('\n'.join(lines))


def generate_endpoints_v2(swagger, app_file, model_file, api_name):
    """Extract all endpoint definitions from this swagger file and write a python
    module defining all the corresponding FastAPI endpoints
    """

    def swagger_type_to_flask_converter(s):
        mappings = {
            # swagger -> flask
            'string': 'string',
            'integer': 'int',
            'int32': 'int',
            'number': 'float',
        }
        assert s in mappings, f"Don't know how to map swagger type '{s}' of a path parameter to a Flask converter"
        return mappings[s]

    if 'paths' not in swagger:
        log.info(f"No routes defined in {app_file}")
        return

    log.info(f"Regenerating {app_file}")

    lines_header = [
        '# This is an auto-generated file - DO NOT EDIT!!!',
        'from flask_cors import cross_origin',
        'from typing import Optional',
        'from pydantic import BaseModel',
        'from pymacaron.endpoint import pymacaron_flask_endpoint',
        'from pymacaron.log import pymlogger',
        '',
        '',
        'log = pymlogger(__name__)',
        '',
        '',
        'def load_endpoints(app=None, error_callback=None):',
        '    from pymacaron import apipool',
        '',
    ]

    lines_imports = []

    lines_endpoints = [
    ]

    for route in swagger['paths'].keys():
        for http_method, endpoint_def in swagger['paths'][route].items():

            http_method = http_method.upper()

            # Extract path, query and body parameters from in declaration
            query_params = {}
            form_params = {}
            path_params = {}
            str_body_model_name = 'None'

            if 'parameters' in endpoint_def:
                for param in endpoint_def['parameters']:
                    err_str = f'{param} of route {http_method}:{route} in api "{api_name}"'
                    assert 'in' in param, f"Missing 'in' declaration {err_str}"
                    if param['in'] == 'path':
                        assert 'name' in param and 'type' in param, f"Missing 'name' and/or 'type' declaration for path paramater {err_str}"
                        path_params[param['name']] = param['type']
                    elif param['in'] == 'query':
                        assert 'name' in param and 'type' in param, f"Missing 'name' and/or 'type' declaration for query paramater {err_str}"
                        query_params[param['name']] = param['type']
                    elif param['in'] == 'body':
                        assert 'schema' in param, f"Missing 'schema' declaration for body parameter {err_str}"
                        assert '$ref' in param['schema'], f"Missing '$ref' declaration in schema of body parameter {err_str}"
                        s = ref_to_model_name(param['schema']['$ref'])
                        str_body_model_name = f'"{s}"'
                    elif param['in'] == 'formData':
                        assert 'name' in param, f"Missing 'name' declaration for formData parameter {err_str}"
                        assert 'type' in param, f"Missing 'type' declaration for formData parameter {err_str}"
                        assert param['type'] == 'file', f"Type {param['type']} is not supported for formData in parameter {err_str}"
                        form_params[param['name']] = param['type']
                    else:
                        assert 0, f"param type {param['in']} not supported yet in parameter {err_str}"

            # What does the endpoint produces?
            assert 'produces' in endpoint_def, f"Missing 'produces' in declaration of endpoint {http_method}:{route} in api '{api_name}'"
            produces = endpoint_def['produces'][0]
            assert produces == 'application/json'

            # Model returned?
            assert 'responses' in endpoint_def, f"Missing 'responses' in declaration of endpoint {http_method}:{route} in api '{api_name}'"
            result_models_lines = []
            for response_type, response_def in endpoint_def['responses'].items():
                assert 'schema' in response_def, f"Missing 'schema' in response '{response_type}' in declaration of endpoint {http_method}:{route} in api '{api_name}'"
                assert '$ref' in response_def['schema'], f"Missing '$ref' in response '{response_type}' in declaration of endpoint {http_method}:{route} in api '{api_name}'"
                s = ref_to_model_name(response_def['schema']['$ref'])
                result_models_lines += [
                    f'                apipool.{api_name}.{s},',
                ]

            # Extract x-bind-server
            operation_id = None
            if 'operationId' in endpoint_def:
                operation_id = endpoint_def['operationId']
            elif 'x-bind-server' in endpoint_def:
                operation_id = endpoint_def['x-bind-server']
            else:
                raise Exception(f"Endpoint {http_method}:{route} has no 'x-bind-server' or 'operationId' declaration")
            method_path = '.'.join(operation_id.split('.')[0:-1])
            method_name = operation_id.split('.')[-1]
            unique_method_name = 'f_' + operation_id.replace('.', '_')

            # Name the endpoint
            def_name = f'endpoint_{http_method.lower()}_' + re.sub(r'\W+', '', str(route).replace('/', '_'))

            # Import the method that implements the endpoint and apply its decorator, if any
            if 'x-decorate-server' in endpoint_def:
                s = endpoint_def['x-decorate-server']
                decorator_f = s.split('.')[-1]
                decorator_pkg = '.'.join(s.split('.')[0:-1])

                # Rename unique_method_name to indicate that it is decorated
                # (so as to not conflict with the same method imported without
                # decorator)
                unique_method_name = f'{unique_method_name}_via_{decorator_f}'

                lines_imports += [
                    '',
                    f'    from {method_path} import {method_name} as {unique_method_name}',
                    f'    from {decorator_pkg} import {decorator_f}',
                    f'    {unique_method_name} = {decorator_f}({unique_method_name})',
                ]
            else:
                lines_imports += [
                    '',
                    f'    from {method_path} import {method_name} as {unique_method_name}',
                ]

            # Compile flask route from swagger route (s/{}/<>/ + add :type)
            flask_route = str(route)
            for name, typ in path_params.items():
                flask_converter = swagger_type_to_flask_converter(typ)
                flask_route = flask_route.replace('{' + name + '}', f'<{flask_converter}:{name}>')

            # If there are query parameters, generate a pydantic model used to
            # parse their string representation
            str_query_model = 'None'
            query_model_lines = []
            if len(query_params):
                str_query_model = 'QueryModel'
                query_model_lines = [
                    '        class QueryModel(BaseModel):',
                ]
                for name, typ in query_params.items():
                    python_type = swagger_type_to_pydantic_type(typ)
                    query_model_lines += [
                        f'            {name}: Optional[{python_type}] = None',
                    ]

            # If there are path parameters, pass them as a dictionary to the
            # generic pymacaron endpoint
            path_args_lines = []
            str_path_params = ''
            if len(path_params):
                str_path_params = ', '.join(path_params.keys())
                for name in path_params.keys():
                    path_args_lines += [
                        f'                "{name}": {name},',
                    ]


            # If there are path parameters, pass them as a dictionary to the
            # generic pymacaron endpoint
            form_args_lines = []
            if len(form_params):
                for name, typ in form_params.items():
                    form_args_lines += [
                        f'                "{name}": "{typ}",',
                    ]

            lines_endpoints += [
                '',
                f'    @app.route("{flask_route}", methods=["{http_method}"])',
                '    @cross_origin(headers=["Content-Type", "Authorization"])',
                f'    def {def_name}({str_path_params}):',

            ] + query_model_lines + [
                '        return pymacaron_flask_endpoint(',
                f'            api_name="{api_name}",',
                f'            f={unique_method_name},',
                '            path_args={',
            ] + path_args_lines + [
                '            },',
                '            form_args={',
            ] + form_args_lines + [
                '            },',
                f'            body_model_name={str_body_model_name},',
                f'            query_model={str_query_model},',
                f'            produces="{produces}",',
                '            result_models=[',
            ] + result_models_lines + [
                '            ],',
                '            error_callback=error_callback,',
                '        )',
                f'    log.info("Binding [{api_name}] {http_method} {route} ==> {operation_id}")',
                '',
            ]

    # log.info("GET /api/v4/chat/<chat_id>/message/<message_id> ==> gofrendly.v4.message.do_get_message")
    # @app.route('/api/v4/chat/<str:chat_id>/message/<str:message_id>', methods=['GET'])
    # def endpoint_do_get_message(chat_id, message_id):
    #     from gofrendly.v4.message import do_get_message
    #     return pymacaron_flask_endpoint(
    #         api_name='chat',
    #         f=do_get_message,
    #         path_args={
    #             'chat_id': chat_id,
    #             'message_id': message_id,
    #         },
    #         body_model_name=None,
    #         query_model=None,
    #     )

    # log.info("GET /api/v4/chat/<chat_id>/message/add ==> gofrendly.v4.message.do_post_message")
    # @app.route('/api/v4/chat/<str:chat_id>/message/add', methods=['POST'])
    # def endpoint_do_post_message(chat_id):
    #     from gofrendly.v4.message import do_post_message
    #     return pymacaron_flask_endpoint(
    #         api_name='chat',
    #         f=do_post_message,
    #         path_args={
    #             'chat_id': chat_id,
    #         },
    #         body_model_name='v4NewChatMessage',
    #         query_model=None,
    #     )

    # log.info("GET /api/v4/chat/<chat_id>/messages/search ==> gofrendly.v4.message.do_search_messages")
    # @app.route('/api/v4/chat/<str:chat_id>/messages/search', methods=['GET'])
    # class endpoint_do_search_messages(BaseModel):
    #     class QueryModel(BaseModel):
    #         text: Optional[str] = None
    #         id: Optional[str] = None
    #
    #     from gofrendly.v4.message import do_search_messages
    #     return pymacaron_flask_endpoint(
    #         api_name='chat',
    #         f=do_search_message,
    #         path_args={
    #             'chat_id': chat_id,
    #         },
    #         body_model_name=None,
    #         query_model=QueryModel,
    #     )

    # Optionally: global decorator
    # log.info(...)
    # @app.route('/api/v4/chat/<str:chat_id>/messages/search', methods=['GET'])
    # @global_decorator()
    # class...

    with open(app_file, 'w') as f:
        f.write('\n'.join(lines_header + lines_imports + lines_endpoints))


def load_api_models_and_endpoints(api_name=None, api_path=None, dest_dir=None, model_file=None, app_file=None, create_endpoints=True, force=False, load_code=True):
    """Load all object models defined inside the OpenAPI specification located at
    api_path into a generated python module at dest_dir/[api_name].py

    Optionally generate Flask endpoints and route declarations, binding the
    APIs routes to the methods implementing them, and converting request
    parameters and response to and from pymacaron models.

    If endpoints were generated, return a module object with a load_endpoints()
    method to call with the Flask app in argument.

    """

    if not dest_dir:
        dest_dir = os.path.dirname(api_path)

    if model_file is None:
        model_file = './' + os.path.relpath(os.path.join(dest_dir, f'{api_name}_models.py'))
    if app_file is None:
        app_file = './' + os.path.relpath(os.path.join(dest_dir, f'{api_name}_app.py'))

    #
    # Step 1: Regenerate pydantic and FastAPI python code, if needed
    #

    # Should we re-generate the models file?
    do_models = False
    if force:
        do_models = True
    elif not os.path.exists(model_file):
        do_models = True
    elif modified_time(model_file) < modified_time(api_path):
        do_models = True

    # Should we re-generate the endpoints file?
    do_endpoints = False
    if create_endpoints:
        if force:
            do_endpoints = True
        elif not os.path.exists(model_file):
            do_endpoints = True
        elif modified_time(model_file) < modified_time(api_path):
            do_endpoints = True

    # Do we need to re-generate anything?
    if do_models or do_endpoints:
        swagger = None

        if api_path.endswith('.yaml'):
            log.info(f"Loading swagger file {api_path}")
            swagger = yaml.load(open(api_path), Loader=yaml.FullLoader)

        if not swagger:
            raise Exception(f"Don't know how to load {api_path}")

        swagger_version = swagger['swagger']
        assert swagger_version == '2.0', f"OpenAPI version '{swagger_version}' is not supported"

        if do_models:
            generate_models_v2(swagger, model_file, api_name)

        if do_endpoints:
            generate_endpoints_v2(swagger, app_file, model_file, api_name)

    else:
        if not do_models:
            log.info(f"No need to regenerate {model_file}")
        if create_endpoints and not do_endpoints:
            log.info(f"No need to regenerate {app_file}")

    #
    # Step 2: Load code
    #

    def do_load_code(path):
        spec = importlib.util.spec_from_file_location(api_name, path)
        pkg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pkg)
        return pkg

    model_pkg = None
    if load_code:
        model_pkg = do_load_code(model_file)

    app_pkg = None
    if create_endpoints:
        app_pkg = do_load_code(app_file)

    #
    # Step 3: Load all pydantic models into apipool
    #

    from pymacaron import apipool

    if model_pkg:
        cnt = 0
        for model_name in model_pkg.__all_models:
            apipool.add_model(api_name, model_name, getattr(model_pkg, model_name))
            cnt += 1

        log.info(f"Loaded {cnt} models from {model_file}")

    return app_pkg
