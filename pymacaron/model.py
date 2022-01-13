import ujson
from pymacaron.log import pymlogger


log = pymlogger(__name__)


class PymacaronBaseModel(object):

    # Those class attributes must be overriden in the child class
    __model_attributes = []
    __model_name = None
    __model_datetimes = []


    # See https://pydantic-docs.helpmanual.io/usage/exporting_models/ about ujson vs orjson
    class Config:
        json_loads = ujson.loads


    def to_json(self):
        """Return a json representation of this PyMacaron object"""

        j = self.json(include=self.__model_attributes)

        # TODO: implement keep_datetime

        return j


    @classmethod
    def from_json(cls, j):
        """Take a json dictionary and return a model instance"""

        # NOTE: the correct way to do this should be to call cls.parse_raw on the string representation of j

        self = type(cls)
        for k in self.__model_attributes:
            if k in j:
                setattr(self, k, j[k])

        return self


    def get_model_name(self):
        """Return the name of the OpenAPI schema object describing this PyMacaron Model instance"""
        return getattr(self, '__model_name')


    def clone(self):
        # Deprecated: should use pydantic.copy() instead
        return self.copy()
