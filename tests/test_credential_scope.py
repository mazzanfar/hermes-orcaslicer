"""Credential env-var names are plugin-scoped and never sent over plaintext http without opt-in."""
from tests.test_workflow import Base
from tests.tools_harness import Tools


class CredentialScopeTests(Base):
    def setUp(self):
        super().setUp()
        self.tools = Tools(self.base)

    def configure(self, name, **params):
        params = {"kind": "octoprint", "printer_profile": "Example 0.4 nozzle", "url": "https://printer.example", **params}
        return self.tools.call("orca_printer_configure", name=name, **params)

    def reject(self, name, **params):
        params = {"kind": "octoprint", "printer_profile": "Example 0.4 nozzle", "url": "https://printer.example", **params}
        return self.tools.reject("orca_printer_configure", name=name, **params)

    def test_unscoped_env_names_are_rejected_everywhere(self):
        for label, params in {
            "api_key_env": {"api_key_env": "OPENROUTER_API_KEY"},
            "password_env": {"kind": "prusalink", "options": {"username": "maker", "password_env": "OPENROUTER_API_KEY"}},
            "access_code_env": {"kind": "flashforge_http", "options": {"serial": "TESTSERIAL", "access_code_env": "OPENROUTER_API_KEY"}},
            "camera_api_key_env": {"options": {"camera_url": "https://cam.example/snapshot", "camera_api_key_env": "OPENROUTER_API_KEY"}},
            "lowercase": {"api_key_env": "orca_key"},
            "bare prefix": {"api_key_env": "ORCA_"},
            "not a string": {"options": {"camera_url": "https://cam.example/snapshot", "camera_api_key_env": 1}},
        }.items():
            with self.subTest(option=label):
                error = self.reject(f"bad-{label.replace(' ', '-')}", **params)
                self.assertIn("ORCA_", error)
                self.assertIn("ORCA_OCTOPRINT_KEY", error)
        self.assertEqual(self.tools.call("orca_printers"), [])

    def test_scoped_env_names_are_accepted(self):
        self.configure("plain", api_key_env="ORCA_X")
        self.configure("hermes-prefixed", api_key_env="HERMES_ORCA_KEY_2")
        self.configure("camera", api_key_env="ORCA_PRINTER", options={"camera_url": "https://cam.example/snapshot", "camera_api_key_env": "ORCA_CAM"})
        names = {printer["name"]: printer for printer in self.tools.call("orca_printers")}
        self.assertEqual(names["plain"]["api_key_env"], "ORCA_X")
        self.assertEqual(names["camera"]["options"]["camera_api_key_env"], "ORCA_CAM")

    def test_credentials_over_plaintext_http_require_explicit_opt_in(self):
        error = self.reject("http-key", url="http://printer.example", api_key_env="ORCA_X")
        self.assertIn("plaintext http", error)
        self.assertIn("allow_plaintext_credentials", error)
        self.assertIn("https://", error)
        error = self.reject("http-password", kind="prusalink", url="http://printer.example", options={"username": "maker", "password_env": "ORCA_PW"})
        self.assertIn("password_env", error)
        error = self.reject("http-camera", options={"camera_url": "http://cam.example/snapshot", "camera_api_key_env": "ORCA_CAM"})
        self.assertIn("camera_url", error)
        self.assertIn("must be a boolean", self.reject("bad-flag", url="http://printer.example", api_key_env="ORCA_X", options={"allow_plaintext_credentials": "yes"}))
        self.assertEqual(self.tools.call("orca_printers"), [])
        # Without credentials, a plaintext URL stays acceptable; with the explicit opt-in, credentials may use it.
        self.configure("http-no-credentials", url="http://printer.example")
        self.configure("http-opt-in", url="http://printer.example", api_key_env="ORCA_X",
                       options={"allow_plaintext_credentials": True, "camera_url": "http://cam.example/snapshot", "camera_api_key_env": "ORCA_CAM"})
        self.assertEqual({p["name"] for p in self.tools.call("orca_printers")}, {"http-no-credentials", "http-opt-in"})
