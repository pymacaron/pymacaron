# klue-microservice

Easily create and deploy a Flask-based REST api running as a Docker container
on amazon AWS Elastic Beanstalk.

[klue-microservice](https://github.com/erwan-lemonnier/klue-microservice) uses
[klue-client-server](https://github.com/erwan-lemonnier/klue-client-server) to
spawn REST apis into a Flask app. These apis are defined as swagger
specifications, describing all API endpoints in a friendly yaml format, and
binding endpoints to Python methods.

[klue-microservice](https://github.com/erwan-lemonnier/klue-microservice) uses
[klue-microservice-deploy](https://github.com/erwan-lemonnier/klue-microservice-deploy)
to easily deploy the micro service as a Docker container running inside Amazon
Elastic Beanstalk.

With [klue-microservice](https://github.com/erwan-lemonnier/klue-microservice),
you get out-of-the-box:

* A best practice auto-scalling setup on Elastic Beanstalk
* Error handling and reporting around your api endpoints
* Endpoint authentication based on JWT tokens
* Python objects for all your api's json data, with silent
marshalling/unmarshalling and validation

Easy peasy now you happy!

## Example

See
[klue-microservice-helloworld](https://github.com/erwan-lemonnier/klue-microservice-helloworld)
for an example of a minimal REST api implemented with klue-microservice, and
ready to deploy on docker containers in Amazon EC2.

## Installation

```
pip install klue-microservice
pip install klue-microservice-deploy
```

## Synopsis

A REST api microservice built with klue-microservice has a directory tree
looking like this:

```
.
├── apis                       # Here you put the swagger specifications both of the apis your
│   └── myservice.yaml         # server is implementing, and of eventual other apis your server
│   └── login.yaml             # is in its turn calling
│   └── profile.yaml           # See klue-client-server for the supported yaml formats.
|
├── myservice                  # Here is the code implementing your server api's endpoints
│   └── api.py
│
├── LICENSE                    # You should always have a licence :-)
├── README.rst                 # and a readme!
|
├── klue-config.yaml           # Config for klue-microservice and klue-microservice-deploy
|
├── server.py                  # Code to start your server, see below
|
└── test                       # Standard unitests, executed with nosetests
|   └── test_pep8.py
|
└── testaccept                 # Acceptance tests against api endpoints:
    ├── test_v1_user_login.py  # Those are black-box tests against a running server
    └── test_version.py

```

And your server simply looks like:

```python
import os
import sys
import logging
from flask import Flask
from klue_microservice import API, letsgo


log = logging.getLogger(__name__)

# WARNING: you must declare the Flask app as shown below, keeping the variable
# name 'app' and the file name 'server.py', since gunicorn is configured to
# lookup the variable 'app' inside the code generated from 'server.py'.

app = Flask(__name__)
# Here you could add custom routes, etc.


def start(port=80, debug=False):

    # Your swagger api files are under ./apis, but you could have them anywhere
    # else really.

    here = os.path.dirname(os.path.realpath(__file__))
    path_apis = os.path.join(here, "apis")

    # Tell klue-microservice to spawn apis inside this Flask app.  Set the
    # server's listening port, whether Flask debug mode is on or not. Other
    # configuration parameters, such as JWT issuer, audience and secret, are
    # fetched from 'klue-config.yaml' or the environment variables it refers to.

    api = API(
        app,
        port=port,
        debug=debug,
    )

    # Find all swagger files and load them into klue-client-server

    api.load_apis(path_apis)

    # Optinally, publish the apis' specifications under the /doc/<api-name>
    # endpoints:
    # api.publish_apis()

    # Start the Flask app and serve all endpoints defined in
    # apis/myservice.yaml

    api.start(serve="myservice")


# Let klue-microservice handle argument parsing and all the scaffholding
letsgo(__name__, callback=start)
```

You start your server in a terminal like this:

```bash
cd projectroot
python server.py --port 8080
```

You run acceptance tests against the above server like this:

```bash
cd projectroot
run_acceptance_tests --local
```

You deploy your api to Amazon Elasticbean like this:

```bash
deploy_pipeline --push --deploy
```


## Deep dive

### Installing

```
pip install klue-microservice
```

Optionally, to deploy to Amazon:

```
pip install klue-microservice-deploy
```

### Swagger specifications

All api endpoints that your service needs, both those it implements and those
it calls as a client, are to be defined as swagger specifications in the format
supported by
[klue-client-server](https://github.com/erwan-lemonnier/klue-client-server).
klue-client-server uses [Bravado](https://github.com/Yelp/bravado) to handle
marshalling/unmarshalling and validation of your api objects to and from json,
and does all the magic of spawning client and server stubs for all api
endpoints, catching errors, and providing optional database serialization for
your api objects.

### JWT authentication

klue-microservice allows you to add JWT token authentication around api
endpoints.

Authentication is achieved by passing a JWT session token in the HTTP
Authorization header of api requests:

```Authorization: Bearer {session token}```

Your service may generate JWT tokens using the 'generate_token()' method from
[klue-microservice.auth](https://github.com/erwan-lemonnier/klue-microservice/blob/master/klue_microservice/auth.py).

The JWT issuer, audience and secret are set via environment variables, whose
names are defined in 'klue-config.yaml'. By default, tokens are valid for 24
hours.

### Error handling and reporting

If an endpoint raises an exception, it will be caught by klue-microservice and returned
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
[KlueMicroServiceException](https://github.com/erwan-lemonnier/klue-microservice/blob/master/klue_microservice/exceptions.py)
and return them as json Error replies at any time as follows:

```python
from klue_microservice.exceptions import KlueMicroServiceException

class InvalidUserError(KlueMicroServiceException):
    code = 'INVALID_USER'        # Sets the value of the 'error' field in the error json object
    status = 401                 # The HTTP reply status, and 'status' field of the error json object

# An endpoint implementation...
def do_login(userdata):
    raise MyException("Sorry, we don't know you")
```

When an exception occurs in your endpoint, you have the choice of:

* If it is a fatal exception, raise a KlueMicroServiceException to the caller as shown above.

* If it is a non-fatal error, you can just ignore it, or you can send back a
crash report to the service's admins by calling the 'report_error()' method
from
[klue-microservice.crash](https://github.com/erwan-lemonnier/klue-microservice/blob/master/klue_microservice/crash.py).

You tell klue-microservice what to do with crash reports by providing the
'klue-microservice.API' constructor with an 'error_reporter' callback:

```python
from klue_microservice import API, letsgo

def my_crash_reporter(title, message):

    # title is a short description of the error, while message is a full json
    # crash dump in string format, containing a traceback of the exception
    # caught, data on the caller and runtime, etc. Now, send it to who you
    # want!

    send_email(to='admin@mysite.com', subject=title, body=message)
    tell_slack(channel='crashes', msg="%s\n%s" % (title, message))

api = API(
    app,
    port=port,
    debug=debug,
    error_reporter=my_crash_reporter,
    ..
)
```

### Testing strategy

klue microservices are developed around two sets of tests:

* Standard Python unitests that should be located under 'test/' and will be
executed via nosetests at the start of the deployment pipeline.

* Blackbox acceptance tests that target the api endpoints, and are executed via
the tool
[run_acceptance_tests](https://github.com/erwan-lemonnier/klue-microservice/blob/master/bin/run_acceptance_tests)
that comes packaged with klue-microservice. Those acceptance tests should be
located under the 'testaccept' directory, and it is recommended to name them
after the endpoint they target. So one test file per tested API
endpoint. Acceptance tests are designed to be executed against a running
instance of the API server, be it a server you are running locally in a
separate terminal, a docker container, or a live instance in Elastic Beanstalk.
Those tests should therefore treat the API as a blackbox and focus solely on
making API calls and testing the results. API calls should be made using test
methods from [klue-unit](https://github.com/erwan-lemonnier/klue-unit). See
[klue-microservice-helloworld](https://github.com/erwan-lemonnier/klue-microservice-helloworld/blob/master/testaccept/test_version.py)
for an example of acceptance tests.

### Deployment pipeline

Klue microservices come with a ready-to-use deployment pipeline that packages
the service as a docker image and deploys it on Amazon Elastic Beanstalk with
little configuration required.

For details, see
[klue-microservice-deploy](https://github.com/erwan-lemonnier/klue-microservice-deploy).

### Elastic Beanstalk configuration

The Klue microservice toolchain is built to deploy services as Docker images
running inside Amazon EC2 instances in Elastic Beanstalk, behind an Elastic
Load Balancer. All the details of setting up those Amazon services is handled
by
[klue-microservice-deploy](https://github.com/erwan-lemonnier/klue-microservice-deploy)
and should be left untouched. A few parameters can be adjusted, though. They
are described in the 'klue-config.yaml' section below.

### klue-config.yaml

The file 'klue-config.yaml' is the one place to find all configurable aspects
of a 'klue-microservice'. The file accepts the following attributes:

* 'name' (MANDATORY): a short name for this project, used when naming elastic
beanstalk environments.

* 'live_host' (MANDATORY): url to the live server running this api.

* 'env_jwt_secret', 'env_jwt_audience', 'env_jwt_issuer' (OPTIONAL): name of
  environment variables containing respectively the JWT secret, JWT audience
  and JWT issuer used for generating and validating JWT tokens. Not needed if
  the API does not use authentication.

* 'env_secrets' (OPTIONAL): names of environment variables that will be passed
  to Elastic Beanstalk and loaded at runtime into the Docker container in
  Elastic Beanstalk. This is the recommended way of passing secrets to the
  container without commiting them inside your code.

The following variables are needed if you want to deploy to Elastic Beanstalk
using
[klue-microservice-deploy](https://github.com/erwan-lemonnier/klue-microservice-deploy):

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
example](https://github.com/erwan-lemonnier/klue-microservice-helloworld/blob/master/klue-config.yaml)
of 'klue-config.yaml'.

### Configuration file object

The content of 'klue-config.yaml' is loaded into a singleton KlueConfig object,
accessible at any time. It is recommended to use this object to store any other
configuration parameters your api requires:

```python
from klue-microservice.config import get_config

# Add your own parameters to the KlueConfig object:
conf = get_config()
conf.my_api_key = 'aeouaeouaeouaeouaeou'
conf.my_api_secret = '2348172438172364'
```

### Built-in endpoints

The following endpoints are built-in into every klue-microservice instance, based
on [this swagger spec](https://github.com/erwan-lemonnier/klue-microservice/blob/master/klue_microservice/ping.yaml):

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

### Defining new Errors

You can define your own Exceptions extending 'KlueMicroServiceException' by
calling the 'add_error' method as below:

```
from klue_microservice.exceptions import add_error

# add_error() generates a class named MyOwnException that inherits from
# KlueMicroServiceException and is properly handled by
# klue-microservice. add_error() returns the MyOwnException class

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

from myexceptions import MyChildOfKlueMicroServiceException

def my_endpoint_implementation():

    # You can raise an exception: it will be considered as an internal server
    # error and reported as a json Error with status=500 and error code set to
    # 'UNHANDLED_SERVER_ERROR' and error message set to 'wtf!'
    raise Exception('wtf!')

    # Or, much better, you can raise a custom exception that subclasses
    # KlueMicroServiceException: it will automatically be converted into an
    # Error json, with the proper status, error code and error message set, and
    # returned to the caller
    raise MyChildOfKlueMicroServiceException('wtf!')

    # You could also just return an instance of KlueMicroServiceException
    return MyChildOfKlueMicroServiceException('wtf!')

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

You can configure klue-microservice to send error reports anywhere you want
(email, slack, etc.) by setting an 'error_reporter' (see above). Once you have
done it, any call to 'report_error()' will send a crash report via the
'error_reporter'.

If you want to report an error that occured while calling an other api:

```python
from klue_microservice.exceptions import is_error
from klue_microservice.crash import report_error

profile = ApiPool.user.client.get_profile()

# Did the 'get_profile' endpoint return an Error object?
if is_error(profile):
    # Send a crash report to your admins, including the error object
    report_error("Oops. Failed to get user profile", caught=profile)
```

The crash report above will have an auto-generated title starting with the
text 'NON-FATAL BACKEND ERROR', to differentiate from crash reports that resulted
from an exception in the server, reported as 'FATAL BACKEND ERROR'.

### Loading api clients from a standalone script

It may come very handy within a standalone script to be able to call REST apis
through the klue-microservice framework, to get object marshalling and error
handling out of the box. It is done as follows:

```python
import flask
from klue.swagger.apipool import ApiPool
from klue_microservice.exceptions import is_error
from klue_microservice import load_clients

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