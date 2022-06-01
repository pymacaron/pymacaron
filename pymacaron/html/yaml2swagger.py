import base64
from typing import Any, Dict, List
import yaml, json, os, datetime

from pymacaron.html.swaggerHTML import SWAGGER, BASETEMPLATE

class YamlParser:
    pwd: str = os.getcwd()
    yml_dir: str = "apis"

    @classmethod
    def read_yaml_file(cls, file:str) -> Dict[str,Any]:
        target_dir = os.path.join(cls.pwd, cls.yml_dir)
        with open(os.path.join(target_dir, file), 'r') as yaml_file:
            data_loaded = yaml.safe_load(yaml_file)
        return data_loaded


    @classmethod
    def identify_yaml_files(cls) -> List[str]:
        target_dir = os.path.join(cls.pwd, cls.yml_dir)
        yaml_files = []
        for file in os.listdir(target_dir):
            if os.path.isfile(os.path.join(target_dir, file)):
                if file.endswith("yaml") or file.endswith("yml"):
                    yaml_files.append(file)

        return yaml_files

    @classmethod
    def convert_to_html(cls, yaml_file: str) -> str:
        def defaultconverter(obj):
            if isinstance(obj, datetime.datetime):
                return obj.__str__()

        json_blob = json.dumps(cls.read_yaml_file(yaml_file), default=defaultconverter)
        return SWAGGER % base64.b64encode(json_blob.encode('utf-8')).decode('utf-8')

    @classmethod
    def make_router(cls, yaml_files: str) -> str:
        data = []
        for file in yaml_files:
            # Read the yaml file and make sure that is has the required info:
            file_dict = cls.read_yaml_file(file)
            title = file_dict.get("info").get("title", None)
            version = file_dict.get("info").get("version", None)
            assert type(title) == str
            assert type(version) == str

            # If it doesent break:
            data.append({
                "file": file,
                "title": title,
                "version": version,
            })

        return BASETEMPLATE % json.dumps(data)
