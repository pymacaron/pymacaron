import os
import sys
import multiprocessing

sys.path.append('.')


# Configuration file for gunicorn
#
# Run with:
#
# gunicorn --bind 127.0.0.1:8080 --config python:klue_microservice.gunicorn server:app

bind = '127.0.0.1:8080'
backlog = 2048

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'
timeout = 120
keepalive = 2

# With an average of 200 requests/hour, 2000 requests = 10 hours, 2800 = 14 hours
max_requests = 2400
max_requests_jitter = 800

preload = True

errorlog = '-'
loglevel = 'info'
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

proc_name = None

def pre_fork(server, worker):
    pass

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

    # get traceback info
    import threading
    import sys
    import traceback
    id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# Thread: %s(%d)" % (id2name.get(threadId, ""), threadId))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                code.append("  %s" % (line.strip()))
    worker.log.debug("\n".join(code))

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")
