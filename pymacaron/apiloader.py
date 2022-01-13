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


def generate_models(swagger, model_file):
    """Extract all model definitions from this swagger file and write a python
    module defining every corresponding pymacaron model class
    """

    all_models = list(swagger['definitions'].keys())
    all_models.sort()
    str_all_models = ', '.join([f'"{s}"' for s in all_models])


    def def_to_type(o, model_name, attr_name):
        # Take either {'type': <type>, 'format': ...} or {'$ref': '#/definitions/<type>'}
        # and return the type (or format if available)
        assert type(o) is dict, f"Expected a dict instead of '{o}' in definition of {model_name}:{attr_name}"
        t = None
        if '$ref' in o:
            s = o['$ref']
            assert s.startswith("#/definitions/"), f"Failed to parse ref '{s}' in definition of {model_name}:{attr_name}"
            log.info(f"Looking at def '{o}'")
            t = s.split('/')[-1].replace("'", "").replace('"', '').strip()
        elif 'format' in o:
            t = o['format']
        elif 'type' in o:
            t = o['type']
        else:
            raise Exception(f"Don't know how to identify type in '{o}' definition of {model_name}:{attr_name}")

        return swagger_to_python_type(t, all_models, model_name, attr_name)


    log.info(f"Regenerating {model_file}")
    lines = [
        '# This is an auto-generated file - DO NOT EDIT!!!',
        'from pymacaron.model import PymacaronBaseModel',
        'from pydantic import BaseModel',
        'from typing import List',
        'from datetime import datetime',
        '',
        f'__all_models = [{str_all_models}]',
        '',
    ]

    # Now comes a tricky part: we need to sort class declarations so that
    # classes are declared before they are used in the type constraints of
    # other classes

    for model_name, model_def in swagger['definitions'].items():

        properties = list(model_def['properties'].keys())
        properties.sort()
        str_properties = ', '.join([f'"{s}"' for s in properties])

        lines += [
            '',
            f'class {model_name}(BaseModel, PymacaronBaseModel):',
            f'    __model_name = "{model_name}"',
            f'    __model_attributes = [{str_properties}]',
            '    __model_datetimes = []',
            '',
        ]

        for p_name, p_def in model_def['properties'].items():
            # Looking at the properties definition, typically one of:
            #
            # type: string
            #
            #
            # type: str
            # format: datetime
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
                lines.append(f'    {p_name}: List[{t}]')

            else:
                t = def_to_type(p_def, model_name, p_name)
                lines.append(f'    {p_name}: {t}')

    lines.append('')
    lines.append('')

    with open(model_file, 'w') as f:
        f.write('\n'.join(lines))


def generate_endpoints(swagger, app_file, model_file):
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

        if do_models:
            generate_models(swagger, model_file)

        if do_endpoints:
            generate_endpoints(swagger, app_file, model_file)

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

    for model_name in pkg.__all_models:
        apipool.add_model(api_name, model_name, getattr(pkg, model_name))


    #
    # Step 3: TODO: Load FastAPI endpoints??
    #
