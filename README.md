![pymacaron logo](https://github.com/pymacaron/pymacaron/blob/master/logo/pymacaron-logo-small.png)

# PyMacaron

Python microservice framework based on Flask, OpenAPI, docker and AWS/beanstalk.

## In short

Create and deploy a Flask-based REST api running as a Docker container on
amazon AWS Elastic Beanstalk, in 3 steps:

* Write a swagger specification for your api
* Tell which Python method to execute for every swagger endpoint
* Implement the Python methods

BOOM! Your are live on Amazon AWS!

PyMacaron abstracts away all the scaffholding of structuring your Python app,
defining routes, serializing/deserializing between json, Python objects and
databases, containerizing your app and deploying it on Amazon.

What's left in your codebase is the only thing that matters: your business
logic.


## In more detail

[pymacaron](https://github.com/pymacaron/pymacaron) uses
[pymacaron-core](https://github.com/pymacaron/pymacaron-core) to
spawn REST apis into a Flask app. These apis are defined as swagger
specifications, describing all API endpoints in a friendly yaml format, and
binding endpoints to Python methods.

[pymacaron](https://github.com/pymacaron/pymacaron) uses
[pymacaron-aws](https://github.com/pymacaron/pymacaron-aws)
to easily deploy the micro service as a Docker container running inside Amazon
Elastic Beanstalk.

[pymacaron](https://github.com/pymacaron/pymacaron) gives
you:

* A best practice auto-scalling setup on Elastic Beanstalk
* Error handling and reporting around your api endpoints (via slack or email)
* Endpoint authentication based on JWT tokens
* Transparent mapping from json and DynamoDB to Python objects
* Automated validation of API data and parameters
* A structured way of blackbox testing your API, integrated in the deploy pipeline
* A production-grade stack (docker/gunicorn/Flask)

## Example

See
[pymacaron-helloworld](https://github.com/pymacaron/pymacaron-helloworld)
for an example of a minimal REST api implemented with pymacaron, and
ready to deploy on docker containers in Amazon EC2.

## Your first server

Install pymacaron:

```
pipenv install pymacaron
pipenv install pymacaron-aws
```

A REST api microservice built with pymacaron has a directory tree
looking like this:

```
.
├── apis                       # Here you put the swagger specifications both of the apis your
│   └── myservice.yaml         # server is implementing, and optionally of 3rd-party apis used
│   └── sendgrid.yaml          # by your server.
│   └── auth0.yaml             # See pymacaron-core for the supported yaml formats.
|
├── myservice
│   └── api.py                 # Implementation of your api's endpoints
│
├── LICENSE                    # You should always have a licence :-)
├── README.rst                 # and a readme!
|
├── pym-config.yaml           # Settings for pymacaron and pymacaron-aws
|
├── server.py                  # Code to start your server, see below
|
└── test                       # Standard unitests, executed with nosetests
|   └── test_pep8.py
|
└── testaccept                 # Acceptance tests for your api:
    ├── test_v1_user_login.py  # Black-box tests executed against a running server
    └── test_version.py

```

You start your server by going into the project's root directory and doing:

```bash
python server.py --port 8080
```

Where 'server.py' typically looks like:

```python
import os
import sys
import logging
from flask import Flask
from flask_cors import CORS
from pymacaron import API, letsgo


log = logging.getLogger(__name__)


# WARNING: you must declare the Flask app as shown below, keeping the variable
# name 'app' and the file name 'server.py', since gunicorn is configured to
# lookup the variable 'app' inside the code generated from 'server.py'.

app = Flask(__name__)
CORS(app)
# Here you could add custom routes, etc.


def start(port=80, debug=False):

    # Your swagger api files are under ./apis, but you could have them anywhere
    # else really.

    here = os.path.dirname(os.path.realpath(__file__))
    path_apis = os.path.join(here, "apis")

    # Tell pymacaron to spawn apis inside this Flask app.  Set the
    # server's listening port, whether Flask debug mode is on or not. Other
    # configuration parameters, such as JWT issuer, audience and secret, are
    # fetched from 'pym-config.yaml' or the environment variables it refers to.

    api = API(
        app,
        port=port,
        debug=debug,
    )

    # Find all swagger files and load them into pymacaron-core

    api.load_apis(path_apis)

    # Optionally, publish the apis' specifications under the /doc/<api-name>
    # endpoints, so you may open them in Swagger-UI:
    # api.publish_apis()

    # Start the Flask app and serve all endpoints defined in
    # apis/myservice.yaml

    api.start(serve="myservice")


# Entrypoint
letsgo(__name__, callback=start)
```


You run acceptance tests against the above server (started in a separate
terminal) like this:

```bash
cd projectroot
run_acceptance_tests --local
```

You deploy your api to Amazon Elasticbean like this:

```bash
deploy_pipeline --push --deploy
```


## Bootstraping example

Bootstrap your project by cloning [pymacaron-helloworld](https://github.com/pymacaron/pymacaron-helloworld).

## Pluggable features

[pymacaron](https://github.com/pymacaron/pymacaron) in
itself lets you just define an API server and run it locally. You may use
additional features by installing the following extra modules:

### Asynchronous task execution

Install [pymacaron-async](https://github.com/pymacaron/pymacaron-async) by
following [these instructions](https://github.com/pymacaron/pymacaron-async#setup).

### Deploying as a container in Amazon Beanstalk

Install [pymacaron-aws](https://github.com/pymacaron/pymacaron-aws) by
following [these instructions](https://github.com/pymacaron/pymacaron-aws#setup).

### Use PyMacaron's own testing framework

A [convenient library](https://github.com/pymacaron/pymacaron-unit) for black-box testing your API endpoints:


## Deep dive

### Installing

```
pipenv install pymacaron
```

### Swagger specifications

All api endpoints that your service needs, both those it implements and those
it calls as a client, are to be defined as swagger specifications in the format
supported by [pymacaron-core](https://github.com/pymacaron/pymacaron-core).
pymacaron-core uses [Bravado](https://github.com/Yelp/bravado) to handle
marshalling/unmarshalling and validation of your api objects to and from json,
and does all the magic of spawning client and server stubs for all api
endpoints, catching errors, and providing optional database serialization for
your api objects.


### JWT authentication

pymacaron allows you to add JWT token authentication around api
endpoints.

Authentication is achieved by passing a JWT session token in the HTTP
Authorization header of api requests:

```Authorization: Bearer {session token}```

Alternatively, you may pass the session token as a cookie named 'token' and
containing the string 'Bearer {session token}'.

Your service should generate JWT tokens using the 'generate_token()' method
from
[pymacaron.auth](https://github.com/pymacaron/pymacaron/blob/master/pymacaron/auth.py).

The JWT issuer, audience and secret should be set via 'pym-config.yaml'
(details further down). By default, tokens are valid for 24 hours.

JWT tokens issued by pymacaron always have a 'sub' field set to a user ID. You
may set this user ID when generating tokens as an argument to
'pymacaron.auth.generate_token()', or let pymacaron use the default user ID
defined in 'pymacaron.config.get_config().default_user_id'.



### Error handling and reporting

If an endpoint raises an exception, it will be caught by pymacaron and returned
to the caller in the form of an Error json object looking like:

```json
{
    "error": "INVALID_USER",                      # Code identifying this error
    "error_description": "DB entry not found",    # Developer friendly explanation
    "user_message": "Sorry, we don't know you",   # User friendly explanation (optional)
    "status": 401                                 # Same as the response's HTTP status code
}
```

You can create your own errors by subclassing the class
[PyMacaronException](https://github.com/pymacaron/pymacaron/blob/master/pymacaron/exceptions.py)
and return them as json Error replies at any time as follows:

```python
from pymacaron.exceptions import PyMacaronException

class InvalidUserError(PyMacaronException):
    code = 'INVALID_USER'        # Sets the value of the 'error' field in the error json object
    status = 401                 # The HTTP reply status, and 'status' field of the error json object

# An endpoint implementation...
def do_login(userdata):
    raise MyException("Sorry, we don't know you")
```

When an exception occurs in your endpoint, you have the choice of:

* If it is a fatal exception, raise a PyMacaronException to the caller as shown above.

* If it is a non-fatal error, you can just ignore it, or you can send back a
crash report to the service's admins by calling the 'report_error()' method
from
[pymacaron.crash](https://github.com/pymacaron/pymacaron/blob/master/pymacaron/crash.py).

You tell pymacaron what to do with crash reports by providing the
'pymacaron.API' constructor with an 'error_reporter' callback:

```python
from pymacaron import API, letsgo

def my_crash_reporter(title, message):

    # title is a short description of the error, while message is a full json
    # crash dump in string format, containing a traceback of the exception
    # caught, data on the caller and runtime, etc. Now, send it to who you
    # want!

    send_email(to='admin@mysite.com', subject=title, body=message)
    tell_slack(channel='crashes', msg="%s\n%s" % (title, message))

def start(port=80, debug=False):

    api = API(
        app,
        port=port,
        debug=debug,
        error_reporter=my_crash_reporter,
        ..
    )

letsgo(__name__, callback=start)
```


### Testing strategy

PyMacaron microservices are developed around two sets of tests:

* Standard Python unitests that should be located under 'test/' and will be
executed via nosetests at the start of the deployment pipeline.

* Blackbox acceptance tests that target the api endpoints, and are executed via
the tool
[run_acceptance_tests](https://github.com/pymacaron/pymacaron/blob/master/bin/run_acceptance_tests)
that comes packaged with pymacaron. Those acceptance tests should be
located under the 'testaccept' directory, and it is recommended to name them
after the endpoint they target. So one test file per tested API
endpoint. Acceptance tests are designed to be executed against a running
instance of the API server, be it a server you are running locally in a
separate terminal, a docker container, or a live instance in Elastic Beanstalk.
Those tests should therefore treat the API as a blackbox and focus solely on
making API calls and testing the results. API calls should be made using test
methods from [pymacaron-unit](https://github.com/pymacaron/pymacaron-unit). See
[pymacaron-helloworld](https://github.com/pymacaron/pymacaron-helloworld/blob/master/testaccept/test_version.py)
for an example of acceptance tests.


### Deployment pipeline

PyMacaron microservices come with a ready-to-use deployment pipeline that packages
the service as a docker image and deploys it on Amazon Elastic Beanstalk with
little configuration required.

For details, see
[pymacaron-aws](https://github.com/pymacaron/pymacaron-aws).


### Elastic Beanstalk configuration

The PyMacaron microservice toolchain is built to deploy services as Docker
images running inside Amazon EC2 instances in Elastic Beanstalk, behind an
Elastic Load Balancer. All the details of setting up those Amazon services is
handled by [pymacaron-aws](https://github.com/pymacaron/pymacaron-aws) and
should be left untouched. A few parameters can be adjusted, though. They are
described in the 'pym-config.yaml' section below.


### pym-config.yaml - A global configuration object

The file 'pym-config.yaml' is the one place to find all configurable variables
used by PyMacaron microservices.

The content of 'pym-config.yaml' is automatically loaded into a singleton
object, accessible at any time by calling:

```python
from pymacaron.config import get_config

# You can access all key-values defined in pym-config.yaml:

print get_config().live_host

# And you can defined additional values of your own, though it is recommended
# to add all static values directly in pym-config.yaml to avoid race
# conditions at import time

get_config().my_api_key = 'aeouaeouaeouaeouaeou'
get_config().my_api_secret = '2348172438172364'
```

As described below, one attribute of 'pym-config.yaml' that pymacaron
supports is 'env_secrets': its value should be a list of environment variables
that will be automatically imported into Elastic Beanstalk and loaded at
runtime into the server's Docker container. This is the recommended way of
passing secrets into EC2 instances without commiting them inside your code.

All config attributes whose value matches one of the names listed in
'env_secrets' will automatically have the content of the corresponding
environment variable substituted to their value. This is very convenient when
putting secrets in 'pym-config.yaml', as shown below:

```yaml
# So, assuming you have set the environment variable MY_AWS_SECRET,
# your aws user configuration becomes as simple as:

aws_default_region: eu-central-1
aws_access_key_id: OTh0KhP89JKiudehIasd90blr
aws_secret_access_key: MY_AWS_SECRET

env_secrets:
  - MY_AWS_SECRET

# And 'aws_secret_access_key' will automagically have its value replaced with
# the value of the environment variable MY_AWS_SECRET
```

### pym-config.yaml - Expected key-values

pymacaron expects the following attributes to be set in
'pym-config.yaml':

* 'name' (MANDATORY): a short name for this project, also used when naming
  elastic beanstalk environments.

* 'live_host' (MANDATORY): url to the live server running this api.

* 'env_secrets' (OPTIONAL): names of environment variables that will be passed
  to Elastic Beanstalk and loaded at runtime into the Docker container in
  Elastic Beanstalk. This is the recommended way of passing secrets to the
  container without commiting them inside your code. Other config attributes
  whose value is one of the names listed in 'env_secrets' will have their value
  automatically substituted with the content of the environment variable.

* 'jwt_secret', 'jwt_audience', 'jwt_issuer' (OPTIONAL): values, or names of
  environment variables containing these values, setting respectively the JWT
  secret, JWT audience and JWT issuer used for generating and validating JWT
  tokens. Not needed if the API does not use authentication.

* 'default_user_id' (OPTIONAL): the default user ID to use when generating JWT
  tokens.

The following variables are needed if you want to deploy to Elastic Beanstalk
using
[pymacaron-aws](https://github.com/pymacaron/pymacaron-aws):

* 'aws_user' (MANDATORY): name of the IAM user to use when creating the
  Beanstalk environment.

* 'aws_keypair' (MANDATORY): name of the ssh keypair to deploy on the server's
  EC2 instances.

* 'aws_instance_type' (MANDATORY): the type of EC2 instance to run servers on
  (ex: 't2.micro').

* 'aws_cert_arn' (OPTIONAL): amazon ARN of a SSL certificate to use in the
  service's load balancer. If specified, the live service will be configured to
  listen on port 443 (https). If not, if will listen on port 80 (http).

* 'docker_repo' (MANDATORY): name of the hub.docker.com organization or user to
  which to upload docker images, and from which Amazon will retrieve those
  images.

* 'docker_bucket' (MANDATORY): name of the Amazon S3 bucket to which to upload
  the service's Amazon configuration.

[Here is an
example](https://github.com/pymacaron/pymacaron-helloworld/blob/master/pym-config.yaml)
of 'pym-config.yaml'.


### Built-in endpoints

The following endpoints are built-in into every pymacaron instance, based
on [this swagger spec](https://github.com/pymacaron/pymacaron/blob/master/pymacaron/ping.yaml):

```
# Assuming you did in a separate terminal:
# $ python server.py --port 8080

$ curl http://127.0.0.1:8080/ping
{}

$ curl http://127.0.0.1:8080/version
{
  "container": "",
  "name": "ping",
  "version": "0.0.1"
}

$ curl http://127.0.0.1:8080/auth/version
{
  "error_description": "There is no Authorization header in the HTTP request",
  "error_id": "17f900c8-b456-4a64-8b2b-83c7d36353f6",
  "status": 401,
  "error": "AUTHORIZATION_HEADER_MISSING"
}

$ curl -H "Authorization: Bearer eyJpc3M[...]y8kNg" http://127.0.0.1:8080/auth/version
{
  "container": "",
  "name": "ping",
  "version": "0.0.1"
}

```


## Recipes


### Asynchronous task execution

pymacaron comes with built-in support for asynchronous method execution
by way of Celery and Redis. All you need to do is to add the 'with_async'
key in 'pym-config.yaml':

```yaml
with_async: true
```

And decorate asynchronous methods as follows:

```python
from pymacaron_async import asynctask
from pymacaron_core.swagger.apipool import ApiPool

# Make send_email into an asynchronously executable method, called via celery
@asynctask
def send_email(title, body):
    # Call 3-rd party emailing API pass
    pass

# API endpoint, defined in your swagger API spec
def do_signup_user():
    do_stuff()

    # Schedule a task sending this email and go on, not waiting for the result
    send_email.fire('Welcome!', 'You now have an account')

    return ApiPool.myapi.model.Ok()
```

That's all. Read more about it on [pymacaron-async's github
page](https://github.com/pymacaron/pymacaron-async).


### Defining new Errors

You can define your own Exceptions extending 'PyMacaronException' by
calling the 'add_error' method as below:

```
from pymacaron.exceptions import add_error

# add_error() generates a class named MyOwnException that inherits from
# PyMacaronException and is properly handled by
# pymacaron. add_error() returns the MyOwnException class

exceptionclass = add_error(
    name='MyOwnException',
    code='MY_OWN_EXCEPTION',
    status=401,
)

# You can then inject the MyOwnException into the current module's namespace
globals()['MyOwnException'] = exceptionclass

# And now you can import it in other modules as well
# from myexceptions import MyOwnException

```


### Returning errors

You have multiple ways to let your API endpoint return an Error object. Pick one of the following:

```

from myexceptions import MyChildOfPyMacaronException

def my_endpoint_implementation():

    # You can raise an exception: it will be considered as an internal server
    # error and reported as a json Error with status=500 and error code set to
    # 'UNHANDLED_SERVER_ERROR' and error message set to 'wtf!'
    raise Exception('wtf!')

    # Or, much better, you can raise a custom exception that subclasses
    # PyMacaronException: it will automatically be converted into an
    # Error json, with the proper status, error code and error message set, and
    # returned to the caller
    raise MyChildOfPyMacaronException('wtf!')

    # You could also just return an instance of PyMacaronException
    return MyChildOfPyMacaronException('wtf!')

    # Or you can return an Error model instance (not recommended)
    return ApiPool.myapi.model.Error(
        status=543,
        error='ANOTHER_CUSTOM_ERROR',
        error_description='wtf!',
    )
```

All the methods above will make your endpoint return a flask Response object
with the Error model json-encoded in its body and a status code set to that of
the Error instance.


### Automated crash reporting

Any api endpoint returning an Error instance with a status code above or equal
to 500 will trigger a crash report (ie a call to the error_reporter callback).

And endpoint that takes longer than 5sec to execute will also trigger a crash
report.


### Reporting errors with 'report_error()'

You can configure pymacaron to send error reports anywhere you want
(email, slack, etc.) by setting an 'error_reporter' (see above). Once you have
done it, any call to 'report_error()' will send a crash report via the
'error_reporter'.

If you want to report an error that occured while calling an other api:

```python
from pymacaron.exceptions import is_error
from pymacaron.crash import report_error

profile = ApiPool.user.client.get_profile()

# Did the 'get_profile' endpoint return an Error object?
if is_error(profile):
    # Send a crash report to your admins, including the error object
    report_error("Oops. Failed to get user profile", caught=profile)
```

The crash report above will have an auto-generated title starting with the
text 'NON-FATAL BACKEND ERROR', to differentiate from crash reports that resulted
from an exception in the server, reported as 'FATAL BACKEND ERROR'.


### Decorating errors with 'error_decorator'

You can optionally intercept and manipulate all errors returned by a PyMacaron
microservice by specifying an 'error_decorator' hook as follows:

```python
from pymacaron import API, letsgo

def my_error_decorator(error):
    # Get errors in json format, and return the decorated error
    # In this example: we set a generic 'user_message' that is more
    # friendly that the error_description
    error['user_message'] = 'Something went really wrong! Try again later'
    return error

def start(port=80, debug=False):

    api = API(
        app,
        port=port,
        debug=debug,
        error_decorator=my_error_decorator,
        ..
    )

letsgo(__name__, callback=start)
```

### Automated reporting of slow calls

If an endpoint call exceeds the value 'get_config().report_call_exceeding_ms',
which by default is set to 1000 milliseconds, an error report will be sent with
the 'error_reporter' callback warning of a slow call.

You can change this default limit globally with:

```python
from pymacaron.config import get_config()

# Set the maximum call time to 5 sec - Slower calls trigger an error report
get_config().report_call_exceeding_ms = 5000

```

Or you can do it on a per endpoint basis, using a decorator around the endpoint
methods:

```python
from pymacaron.crash import report_slow

# Set the maximum call time for 'do_login_user' to 5 sec
# Slower calls trigger an error report
@report_slow(max_ms=5000)
def do_login_user(login_data):
    ...
    return ApiPool.login.model.AuthToken(...)
```


### Loading api clients from a standalone script

It may come very handy within a standalone script to be able to call REST apis
through the pymacaron framework, to get object marshalling and error
handling out of the box. It is done as follows:

```python
import flask
from pymacaron_core.swagger.apipool import ApiPool
from pymacaron.exceptions import is_error
from pymacaron import load_clients

# Declare a Flask app and mock its context
app = flask.Flask(__name__)
with app.test_request_context(''):

    # Then load client libraries against a given set of libraries
    api = API(app)
    api.load_clients(apis=['login', 'search'])

    # And you can now call those apis seamlessly!
    result = ApiPool.login.client.do_login(
        ApiPool.login.model.LoginData(
            name='foobar',
            password='youdontwanttoknow'
        )
    )

    if is_error(result):
        log.error("Oops. Failed to login used")
```
