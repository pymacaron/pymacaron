import os
import yaml
import importlib.util
from pymacaron.log import pymlogger


log = pymlogger(__name__)


def modified_time(path):
    return os.path.getmtime(path)


def swagger_to_python_type(t, models, model_name, attr_name):
    """Given a swagger type or format or ref definition, return its corresponding python type"""
    # Take a swagger type and return the corresponding python type
    if t in models:
        return t

    mapping = {
        'boolean': 'bool',
        'int32': 'int',
        'integer': 'int',
        'string': 'str',
        'number': 'float',
        'date': 'datetime',
        'datetime': 'datetime',
        'date-time': 'datetime',
    }

    assert t in mapping, f"Don't know the python type of swagger type '{t}' in definition of {model_name}:{attr_name}"

    return mapping[t]


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
            t = s.split('/')[-1].replace("'", "").replace('"', '').strip()
        elif 'format' in prop_def:
            t = prop_def['format']
        elif 'type' in prop_def:
            t = prop_def['type']
        else:
            raise Exception(f"Don't know how to identify type in '{prop_def}' definition of {model_name}:{prop_name}")

        return swagger_to_python_type(t, all_models, model_name, prop_name)

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
        'from typing import List, Optional',
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

        (path, cls) = get_parent(model_def)
        x_parent = f'Parent{cls}, ' if cls else ''

        lines += [
            '',
            f'class {model_name}({x_parent}PymacaronBaseModel, BaseModel):',
            '    def get_property_names(self):',
            f'        return [{str_properties}]',
            '    def get_model_api(self):',
            f'        return "{api_name}"',
        ]

        for p_name, p_def in model_def['properties'].items():
            # Looking at the properties definition, typically one of:
            #
            # type: str
            # [format: datetime]
            #
            # ref: '#/definitions/<some_type>
            #
            # type: array
            # items:
            #     ref: '#/definitions/<some_type>
            #
            # type: array
            # items:
            #     type: number
            #

            if p_def.get('type', '').lower() == 'array':
                assert 'items' in p_def, f"Expected 'items' in array definition of {model_name}:{p_name}"
                t = def_to_type(p_def['items'], model_name, p_name)
                lines.append(f'    {p_name}: Optional[List[{t}]] = None')
            else:
                t = def_to_type(p_def, model_name, p_name)
                lines.append(f'    {p_name}: Optional[{t}] = None')

    lines.append('')
    lines.append('')

    with open(model_file, 'w') as f:
        f.write('\n'.join(lines))


def generate_endpoints_v2(swagger, app_file, model_file):
    """Extract all endpoint definitions from this swagger file and write a python
    module defining all the corresponding FastAPI endpoints
    """
    log.info(f"Regenerating {app_file}")
    s = ''
    with open(app_file, 'w') as f:
        f.write(s)


def load_api_models_and_endpoints(api_name=None, api_path=None, dest_path=None, load_models=True, load_endpoints=True):
    """Load all object models defined inside the OpenAPI specification located at
    api_path into a generated python module at dest_path/[api_name].py
    """

    model_file = './' + os.path.relpath(os.path.join(dest_path, f'{api_name}_models.py'))
    app_file = './' + os.path.relpath(os.path.join(dest_path, f'{api_name}_app.py'))

    #
    # Step 1: Regenerate pydantic and FastAPI python code, if needed
    #

    # Should we re-generate the models file?
    do_models = False
    if load_models or load_endpoints:
        if not os.path.exists(model_file):
            do_models = True
        elif modified_time(model_file) < modified_time(api_path):
            do_models = True

    # Should we re-generate the endpoints file?
    do_endpoints = False
    if load_endpoints:
        if not os.path.exists(model_file):
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
            generate_endpoints_v2(swagger, app_file, model_file)

    else:
        if not do_models:
            log.info(f"No need to regenerate {model_file}")
        if not do_endpoints:
            log.info(f"No need to regenerate {app_file}")

    #
    # Step 2: Load pydantic objects into pymacaron.apipool
    #

    from pymacaron import apipool

    spec = importlib.util.spec_from_file_location(api_name, model_file)
    pkg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pkg)

    cnt = 0
    for model_name in pkg.__all_models:
        apipool.add_model(api_name, model_name, getattr(pkg, model_name))
        cnt += 1

    log.info(f"Loaded {cnt} models from {model_file}")

    # TODO: support setting model attributes by calling __init__(**kwargs)

    #
    # Step 3: TODO: Load FastAPI endpoints??
    #


    #
    # Step 4: Remember where the api's swagger file is located
    #

    from pymacaron import apispecs
    apispecs.register_api_path(api_name, api_path)
