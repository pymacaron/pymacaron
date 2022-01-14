import ujson
from datetime import datetime
from pymacaron.log import pymlogger


log = pymlogger(__name__)


class PymacaronBaseModel(object):

    # See https://pydantic-docs.helpmanual.io/usage/exporting_models/ about ujson vs orjson
    class Config:
        json_loads = ujson.loads
        json_encoders = {
            # TODO: make itthe datetime encoding configurable
            datetime: lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }


    def __str__(self):
        """Return a generic string representation of a pymacaron model instance"""
        return f'{self.get_model_name()}(self.dict())'


    def to_json(self, keep_datetime=False):
        """Return a json dictionary representation of this PyMacaron object"""

        if keep_datetime:
            return self.dict()

        # Else let pydantic serialize datetimes to json and back
        s = self.json()
        return ujson.loads(s)


    @classmethod
    def from_json(cls, j):
        """Take a json dictionary and return a model instance"""
        return cls.parse_obj(j)


    def get_model_name(self):
        """Return the name of the OpenAPI schema object describing this PyMacaron Model instance"""
        return type(self).__name__


    def get_model_api(self):
        """Return the name of the api to which this model belongs"""
        raise Exception("Should be overriden in model declaration")


    def get_property_names(self):
        """Return the names of all of the model's properties"""
        raise Exception("Should be overriden in model declaration")

    def clone(self):
        # Deprecated: should use pydantic.copy() instead
        return self.copy()
