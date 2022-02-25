import os
import json
from flask import request, jsonify
from werkzeug import FileStorage
from werkzeug.exceptions import ClientDisconnected
from pydantic.error_wrappers import ValidationError
from pymacaron.log import pymlogger
from pymacaron.utils import timenow
from pymacaron import apipool
from pymacaron import jsonencoders
from pymacaron.model import PymacaronBaseModel
from pymacaron.crash import postmortem
from pymacaron.exceptions import PyMacaronException
from pymacaron.exceptions import UnhandledServerError
from pymacaron.exceptions import InvalidParameterError
from pymacaron.exceptions import BadResponseException
from pymacaron.exceptions import InternalValidationError
from pymacaron.exceptions import RequestTimeout


log = pymlogger(__name__)


def get_form_data(form_args=None):
    # Just extract whatever we can from that form, data or file alike

    try:
        kwargs = request.form.to_dict()
    except ClientDisconnected:
        raise RequestTimeout()

    # Go through all the objects passed in form-data and try converting to something json-friendly
    files = request.files.to_dict()
    for k in list(files.keys()):
        v = files[k]
        if isinstance(v, FileStorage):
            name = v.name
            kwargs[name] = v.read()
        else:
            raise Exception("Support for multipart/form-data containing %s is not implemented" % type(v))

    # If the swagger specified an exact list of form arguments, remove anything
    # that does not match it
    if form_args:
        for k in list(kwargs.keys()):
            if k not in form_args:
                del kwargs[k]

    return kwargs


def get_request_body(api_name, model_name):
    """Return an instantiated pymacaron model containing the request's body or form data"""

    kwargs = {}

    # If the request contained no data, no need to analyze it further
    if len(request.get_data()) != 0:

        # Let's try to convert whatever content-type we got in the request to something json-like
        ctype = request.content_type
        if not ctype:
            # If no content-type specified, assume json
            ctype = 'application/json'

        if ctype.startswith('application/x-www-form-urlencoded'):
            # Get the dict() containing the form's key-values
            kwargs = get_form_data()

        elif ctype.startswith('multipart/form-data'):
            # Store the request's form and files
            kwargs = get_form_data()

        else:
            # Assuming we got a json body
            kwargs = request.get_json(force=True)

    # The pymacaron model class we should instantiate - Let pydantic do all the
    # type checking
    cls = getattr(apipool.get_model(api_name), model_name)

    return cls(**kwargs)


def get_path_and_query_parameters(query_model, path_args):
    # Parse and validate the query arguments (if any)
    d = {}
    if query_model:
        # Let pydantic validate query arguments
        d = query_model.parse_obj(request.args.to_dict()).dict()

    # And add the path arguments (without type checking them: we rely on Flask
    # to have done it)
    d.update(path_args)

    return d


def pymacaron_flask_endpoint(api_name=None, f=None, error_callback=None, query_model=None, body_model_name=None, form_args={}, path_args={}, produces='application/json', result_models=[]):
    """Call endpoint in a try/catch loop handling exceptions"""

    endpoint_method = request.method
    endpoint_path = request.path
    t0 = timenow()

    log.info(" ")
    log.info(" ")
    log.info("=> INCOMING REQUEST %s %s -> %s" % (endpoint_method, endpoint_path, f.__name__))
    log.info(" ")
    log.info(" ")

    try:
        return call_f(
            api_name=api_name,
            f=f,
            query_model=query_model,
            body_model_name=body_model_name,
            path_args=path_args,
            form_args=form_args,
            produces=produces,
            result_models=result_models,
        )

    # Catch ALL exceptions
    except (BaseException, Exception) as e:

        log.error(f"Method {f.__name__} raised exception [{str(e)}]")

        if isinstance(e, ValidationError):
            # Convert this pydantic validation error into a pymacaron one
            e = InvalidParameterError(str(e))

        # Report this exception and tons of info about it
        postmortem(
            f=f,
            t0=t0,
            t1=timenow(),
            exception=e,
        )

        # If it's not a PyMacaronException or a child class of it, it's an
        # unhandled error (aka server crash)
        if not isinstance(e, PyMacaronException):
            e = UnhandledServerError(str(e))

        status = e.status

        if error_callback:
            # The error_callback takes the error instance and returns a json
            # dictionary back
            d = error_callback(e)
            log.info(f"Returning API error (status:{status}): {json.dumps(d, indent=4, sort_keys=True)}")
            r = jsonify(d)
            r.status_code = status
            return r

        return e.jsonify()

    finally:
        log.info(" ")
        log.info("<= DONE %s %s -> %s" % (endpoint_method, endpoint_path, f.__name__))
        log.info(" ")
        log.info(" ")


def call_f(api_name=None, f=None, error_callback=None, query_model=None, body_model_name=None, form_args={}, path_args={}, produces='application/json', result_models=[]):
    """A generic flask endpoint that calls a given pymacaron endpoint
    implementation and handle conversion between query/body parameters,
    pymacaron models and flask response. Also handle error handling and
    optional decoration.

    api_name: name of the api to which this endpoint belongs

    f: reference to the method that implements this endpoint in the pymacaron microservice

    path_query_model_name: name of the pymacaron/pydantic model that defines all of this endpoints query and path parameters

    body_model_name: name of the model that defines the HTTP body data expected by this endpoint (None if none)

    """

    if os.environ.get('PYM_DEBUG', None) == '1':
        log.debug("PYM_DEBUG: Request headers are: %s" % dict(request.headers))

    args = []
    if body_model_name:
        args.append(get_request_body(api_name, body_model_name))

    kwargs = get_path_and_query_parameters(query_model, path_args)

    if form_args:
        kwargs.update(get_form_data(form_args))

    if os.environ.get('PYM_DEBUG', None) == '1':
        log.debug("PYM_DEBUG: Request args are: [args: %s] [kwargs: %s]" % (args, kwargs))

    try:
        result = f(*args, **kwargs)
    except ValidationError as e:
        # A pydantic validation error occuring inside the endpoint is actually
        # a fatal crash. We re-raise it but changed its type
        raise InternalValidationError(str(e)) from e

    if produces == 'application/json':
        assert result_models, "BUG: no result models specified"
        str_result_models = ' or '.join([str(m) for m in result_models])

        if not result:
            raise BadResponseException('Nothing to return in response')

        elif isinstance(result, PymacaronBaseModel):
            # Validate that we got the right model as results
            found = False
            for m in result_models:
                if isinstance(result, m):
                    found = True
            if not found:
                raise BadResponseException(f'Expected to return an instance of {str_result_models}, but got a {result}')

            return jsonify(result.to_json(
                exclude_unset=True,
                exclude_none=False,
                keep_nullable=True,
                keep_datetime=False,
                datetime_encoder=jsonencoders.get_datetime_encoder(),
            ))

        elif ".".join([result.__module__, result.__class__.__name__]) == 'flask.wrappers.Response':
            # result is already a flask response
            return result

        else:
            raise BadResponseException(f'Expected to return an instance of {str_result_models} but got {result} of type {type(result)}')

    else:
        # TODO: implement support for returning html content
        #     if type(result) is not tuple:
        #         e = error_callback(PyMacaronCoreException("Method %s should return %s but returned %s" %
        #                                                   (endpoint.handler_server, endpoint.produces, type(result))))
        #         return _responsify(api_spec, e, 500)

        #     # Return an html page
        #     return result

        assert 0, "Support for returning '{produces}' not implemented yet!"
