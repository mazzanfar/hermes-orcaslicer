"""Exercise the same registered handlers Hermes calls, with isolated storage."""
import json
import os
from unittest.mock import patch

from orca_plugin import register


class Tools:
    def __init__(self, base):
        self.handlers = {}
        with patch.dict(os.environ, {"HERMES_ORCA_HOME": str(base)}):
            register(self)

    def register_tool(self, name, handler, **kwargs):
        self.handlers[name] = handler

    def register_skill(self, name, path):
        assert path.is_file()

    def call(self, tool, **params):
        response = json.loads(self.handlers[tool](params))
        if not response["success"]:
            raise AssertionError(response["error"])
        return response["result"]

    def reject(self, tool, **params):
        response = json.loads(self.handlers[tool](params))
        assert response["success"] is False, response
        return response["error"]
