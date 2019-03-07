import logging
from pymacaron_core.swagger.apipool import ApiPool


log = logging.getLogger(__name__)


def get_object_creator(name):
    def init_object(self, *args, **kwargs):
        log.info("Instantiating api object %s" % name)
        # TODO: look up ApiPool model 'name'
        o = ApiPool.ksting.model.JobUpdate(*args, **kwargs)
        # TODO: Dynamically monkey-patch all methods from o into self
        for m in dir(o):
            setattr(self, m, getattr(o, m)) # -> does not work since self is not subscriptable

    return init_object


# TODO: add to_jon() from_json() to instance
# TODO: add save/load if x-persist

objects = {}

def create_object_class(name):
    global objects
    log.info("Registering object %s" % name)
    if name not in objects:
        # Instantiate an object that will generate the Bravado object when initialized
        objects[name] = type(
            name,
            (object, ),
            {
                'name': name,
                '__init__': get_object_creator(name),
            },
        )
    return objects[name]
