#!/usr/bin/env python

import os
import sys
import logging
import json
from flask import Flask

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pymacaron import API, letsgo


log = logging.getLogger(__name__)


app = Flask(__name__)


def test_crash_reporter(msg, body):

    tmpdir = '/tmp/test-pym-microservice'
    try:
        os.stat(tmpdir)
    except Exception:
        os.mkdir(tmpdir)

    data = {
        'title': msg,
        'body': json.loads(body),
    }

    log.info("Storing crash report into %s/error_report.json" % tmpdir)
    with open(os.path.join(tmpdir, "error_report.json"), "a+") as f:
        f.write(json.dumps(data))


def start(port, debug):

    api = API(
        app,
        port=8765,
        debug=False,
        error_reporter=test_crash_reporter,
    )
    api.load_apis('.', include_crash_api=True)
    api.start(serve="crash")

letsgo(__name__, callback=start)
