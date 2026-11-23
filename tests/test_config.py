"""Configuration regressions, run inside the ESPHome container."""

from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


def minimal_config():
    config = yaml.safe_load((ROOT / "tests/config/minimal.yaml").read_text())
    config["external_components"][0]["source"] = str(ROOT / "components")
    return config


def example_config():
    text = (ROOT / "components/a2dp/yaml/esp32-idf-a2dp-sink.yaml").read_text()
    text = text.replace("!secret wifi_ssid", '"test-network"')
    text = text.replace("!secret wifi_password", '"test-password"')
    config = yaml.safe_load(text)
    config["external_components"][0]["source"] = str(ROOT / "components")
    return config


class ConfigurationTests(unittest.TestCase):
    def validate(self, config):
        with tempfile.TemporaryDirectory(prefix="a2dp-config-") as directory:
            path = Path(directory) / "test.yaml"
            path.write_text(yaml.safe_dump(config, sort_keys=False))
            return subprocess.run(
                ["esphome", "config", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_minimal_hub(self):
        result = self.validate(minimal_config())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bluetooth_stack_requested(self):
        # SDK options are reconciled after to_code(); setting CONFIG_BT_ENABLED
        # directly is insufficient when no built-in BLE component is loaded.
        for mode in ("minimal", "wifi-coex", "wifi-no-coex", "ble"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(
                prefix="a2dp-codegen-"
            ) as directory:
                config = minimal_config()
                if mode.startswith("wifi"):
                    config["wifi"] = {
                        "ssid": "test-network",
                        "password": "test-password",
                    }
                    config["a2dp"]["coexistence"] = {
                        "software_coexistence": mode == "wifi-coex"
                    }
                if mode == "ble":
                    config["esp32_ble_tracker"] = {}
                build_path = Path(directory) / "build"
                config["esphome"]["build_path"] = str(build_path)
                path = Path(directory) / "test.yaml"
                path.write_text(yaml.safe_dump(config, sort_keys=False))
                original = path.read_bytes()
                result = subprocess.run(
                    ["esphome", "compile", "--only-generate", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(path.read_bytes(), original)
                sdkconfig = (build_path / "sdkconfig.a2dp-minimal").read_text()
                for option in ("BT_ENABLED", "BT_BLUEDROID_ENABLED", "BT_CLASSIC_ENABLED"):
                    self.assertIn(f"CONFIG_{option}=y", sdkconfig)
                excluded = set(
                    (build_path / "exclude_components.esphomeinternal")
                    .read_text()
                    .strip()
                    .split(";")
                )
                self.assertNotIn("bt", excluded)
                if mode == "wifi-coex":
                    self.assertNotIn("esp_coex", excluded)
                    self.assertIn("CONFIG_ESP_COEX_SW_COEXIST_ENABLE=y", sdkconfig)
                if mode == "ble":
                    self.assertIn("CONFIG_BTDM_CTRL_MODE_BTDM=y", sdkconfig)

    def test_full_example(self):
        result = self.validate(example_config())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pin_preserves_leading_zeroes(self):
        config = minimal_config()
        config["a2dp"]["pairing_pin"] = "0123"
        result = self.validate(config)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0123", result.stdout)

    def test_numeric_pin_rejected(self):
        config = minimal_config()
        config["a2dp"]["pairing_pin"] = 1234
        result = self.validate(config)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pairing_pin", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
