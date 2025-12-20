import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.config_service import ConfigService


class ConfigServiceTests(unittest.TestCase):
    def test_creates_default_undesired_file(self):
        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "config"
            service = ConfigService(base_dir=base_dir)

            path = base_dir / "undesired_tags.json"
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"tags": []})
            self.assertEqual(service.load_undesired_tags(), [])

    def test_recovers_invalid_json(self):
        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "config"
            base_dir.mkdir(parents=True, exist_ok=True)
            (base_dir / "undesired_tags.json").write_text("{ not valid", encoding="utf-8")

            service = ConfigService(base_dir=base_dir)
            tags = service.load_undesired_tags()

            path = base_dir / "undesired_tags.json"
            self.assertEqual(tags, [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"tags": []})

    def test_save_filters_and_persists(self):
        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "config"
            service = ConfigService(base_dir=base_dir)

            service.save_undesired_tags([" cat ", "DOG", "", 123])

            path = base_dir / "undesired_tags.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload, {"tags": ["cat", "DOG"]})
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())

    def test_merges_lm_studio_override(self):
        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "config"
            base_dir.mkdir(parents=True, exist_ok=True)

            config_payload = {
                "dataset_root": "C:/data",
                "lm_studio": {
                    "enabled": False,
                    "base_url": "http://localhost:8080",
                    "timeout_seconds": 15,
                },
            }
            (base_dir / "config.json").write_text(json.dumps(config_payload), encoding="utf-8")
            override_payload = {"lm_studio": {"enabled": True, "default_model": "granite"}}
            (base_dir / "lm_studio.override.json").write_text(json.dumps(override_payload), encoding="utf-8")

            service = ConfigService(base_dir=base_dir)
            config = service.load_config()

            self.assertEqual(
                config.get("lm_studio"),
                {
                    "enabled": True,
                    "base_url": "http://localhost:8080",
                    "default_model": "granite",
                    "timeout_seconds": 15,
                },
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
