import os
import logging
import subprocess
import psutil
from time import sleep
from pymacaron.test import PyMacaronTestCase


log = logging.getLogger(__name__)


tmpdir = '/tmp/test-pym-microservice'
reportpath = os.path.join(tmpdir, "error_report.json")
try:
    os.stat(tmpdir)
except Exception:
    os.mkdir(tmpdir)


class PyMacaronTests(PyMacaronTestCase):

    def setUp(self):
        super().setUp()
        self.pid = None


    def tearDown(self):
        self.kill_server()


    def start_server(self):
        path_server = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testserver.py')
        log.info("Starting test server at %s" % path_server)
        p = subprocess.Popen([path_server])
        self.pid = p.pid
        log.info("Waiting for test server with pid %s to start" % self.pid)
        sleep(2)

        try:
            p = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            assert 0, "Failed to start testserver"


    def kill_server(self):
        log.info("Killing test server with pid %s" % self.pid)
        if self.pid:
            p = psutil.Process(self.pid)
            p.terminate()

        for p in psutil.process_iter():
            cmd = ' '.join(p.cmdline())
            if cmd.endswith('testserver.py'):
                log.info("PROC FOUND: %s" % p.cmdline())
                p.terminate()
