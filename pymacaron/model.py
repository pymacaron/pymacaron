import ujson
from datetime import datetime
from pymacaron.log import pymlogger


log = pymlogger(__name__)


class PymacaronBaseModel(object):
    """The base class from which all pymacaron model classes inherit. Some of these
    methods are redundant with pydantic, but kept for backward compatibility
    with code using older versions of pymacaron.

    """

    # See https://pydantic-docs.helpmanual.io/usage/exporting_models/ about ujson vs orjson
    class Config:
        json_loads = ujson.loads
        json_encoders = {
            # TODO: make the datetime encoding configurable
            datetime: lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }


    def __str__(self):
        """Return a generic string representation of a pymacaron model instance"""
        return f'{self.get_model_name()}(self.dict())'


    def __prune_none(self, j):
        for k in list(j.keys()):
            v = j[k]
            if v is None:
                del j[k]
            elif type(v) is dict:
                self.__prune_none(v)
            elif type(v) is list:
                for i in v:
                    if type(i) is dict:
                        self.__prune_none(i)


    def to_json(self, keep_datetime=False, prune_none=True):
        """Return a json dictionary representation of this PyMacaron object"""

        if keep_datetime:
            j = self.dict()
        else:
            # Else let pydantic serialize datetimes to json and back
            s = self.json()
            j = ujson.loads(s)

        # pydantic sets undefined attributes to None, which we may want to
        # filter out, for example before saving to datastore
        if prune_none:
            self.__prune_none(j)

        return j


    @classmethod
    def from_json(cls, j):
        """Take a json dictionary and return a model instance"""
        return cls.parse_obj(j)


    def clone(self):
        # Deprecated: should use pydantic.copy() instead
        return self.copy()


    def get_model_name(self):
        """Return the name of the OpenAPI schema object describing this pymacaron Model instance"""
        return type(self).__name__


    def get_model_api(self):
        """Return the name of the api to which this model belongs"""
        raise Exception("Should be overriden in model declaration")


    def get_property_names(self):
        """Return the names of all of the model's properties"""
        raise Exception("Should be overriden in model declaration")
