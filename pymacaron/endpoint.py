import os
from flask import request, jsonify
from werkzeug import FileStorage
from pymacaron.log import pymlogger
from pymacaron.utils import timenow
from pymacaron import apipool
from pymacaron.model import PymacaronBaseModel
from pymacaron.crash import postmortem
from pymacaron.exceptions import PyMacaronException
from pymacaron.exceptions import UnhandledServerError
from pymacaron.exceptions import BadResponseException



log = pymlogger(__name__)


def get_form_data(form_data):
    # Just extract whatever we can from that form, data or file alike
    log.debug("FETCHING FORM DATA: %s" % request.form.to_dict())

    kwargs = request.form.to_dict()

    # Go through all the objects passed in form-data and try converting to something json-friendly
    files = request.files.to_dict()
    for k in list(files.keys()):
        v = files[k]
        if isinstance(v, FileStorage):
            name = v.name
            kwargs[name] = v.read()
        else:
            raise Exception("Support for multipart/form-data containing %s is not implemented" % type(v))

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

    # The pymacaron model class we should instantiate
    cls = getattr(apipool.get_model(api_name), model_name)

    return cls(**kwargs)


def get_path_and_query_parameters(query_model, path_args):
    # Parse and validate the query arguments (if any)
    d = {}
    if query_model:
        d = query_model.parse_str(request.query_string)

    # And add the path arguments (without type checking them: we rely on Flask
    # to have done it)
    d.update(path_args)

    return d


def pymacaron_flask_endpoint(api_name=None, f=None, error_callback=None, query_model=None, body_model_name=None, form_args={}, path_args={}, produces='application/json', result_models=[]):
    """Call endpoint in a try/catch loop handling exceptions"""

    t0 = timenow()

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

    except BaseException as e:
        log.info(f"Method {f.__name__} raised exception [{str(e)}]")

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
            log.info(f"Converted exception to API error {d}")
            r = jsonify(d)
            r.status_code = status
            return r

        return e.jsonify()


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

    endpoint_method = request.method
    endpoint_path = request.path

    log.info(" ")
    log.info(" ")
    log.info("=> INCOMING REQUEST %s %s -> %s" % (endpoint_method, endpoint_path, f.__name__))
    log.info(" ")
    log.info(" ")

    if os.environ.get('PYM_DEBUG', None) == '1':
        log.debug("PYM_DEBUG: Request headers are: %s" % dict(request.headers))

    # TODO: fetch params from Flask request and compile args/kwargs to call f() with
    args = []
    if body_model_name:
        args.append(get_request_body(api_name, body_model_name))
        # try:
        #     args.append(get_request_body(api_name, body_model_name))
        # except BadRequest:
        #     ee = error_callback(ValidationError("Cannot parse json data: have you set 'Content-Type' to 'application/json'?"))
        #     return _responsify(api_spec, ee, 400)

    kwargs = get_path_and_query_parameters(query_model, path_args)

    if form_args:
        kwargs.update(get_form_data(form_args))

    if os.environ.get('PYM_DEBUG', None) == '1':
        log.debug("PYM_DEBUG: Request args are: [args: %s] [kwargs: %s]" % (args, kwargs))

    result = f(*args, **kwargs)

    log.info("<= DONE %s %s -> %s" % (endpoint_method, endpoint_path, f.__name__))
    log.info(" ")
    log.info(" ")

    if produces == 'application/json':
        assert result_models, "BUG: no result models specified"
        str_result_models = ', '.join([str(m) for m in result_models])

        if not result:
            raise BadResponseException('Nothing to return in response')

        elif isinstance(result, PymacaronBaseModel):
            # Were we expecting this result model?
            model = None
            for m in result_models:
                if isinstance(result, m):
                    model = m
            if not model:
                raise BadResponseException(f'Expected to return an instance of {str_result_models} but got {result}')
            return jsonify(result.to_json())

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

    # elif endpoint.produces_json:
    #     if not hasattr(result, '__module__') or not hasattr(result, '__class__'):
    #         e = error_callback(PyMacaronCoreException("Method %s did not return a class instance but a %s" %
    #                                                   (endpoint.handler_server, type(result))))
    #         return _responsify(api_spec, e, 500)

    #     # If it's already a flask Response, just pass it through.
    #     # Errors in particular may be either passed back as flask Responses, or
    #     # raised as exceptions to be caught and formatted by the error_callback
    #     result_type = result.__module__ + "." + result.__class__.__name__
    #     if result_type == 'flask.wrappers.Response':
    #         return result

    #     # We may have got a pymacaron Error instance, in which case
    #     # it has a http_reply() method...
    #     if hasattr(result, 'http_reply'):
    #         # Let's transform this Error into a flask Response
    #         log.info("Looks like a pymacaron error instance - calling .http_reply()")
    #         return result.http_reply()

    #     # Otherwise, assume no error occured and make a flask Response out of
    #     # the result.

    #     # TODO: check that result is an instance of a model expected as response from this endpoint
    #     result_json = api_spec.model_to_json(result)

    #     # Send a Flask Response with code 200 and result_json
    #     r = jsonify(result_json)
    #     r.status_code = 200
    #     return r
