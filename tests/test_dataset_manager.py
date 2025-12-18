from app.services.config_service import ConfigService
from app.services.dataset_manager import DatasetManager


def test_browse_allows_multi_level_navigation(tmp_path):
    config_dir = tmp_path / "config"
    data_root = tmp_path / "data"
    (data_root / "level1" / "level2").mkdir(parents=True)
    (data_root / "level1" / "sibling").mkdir()

    config = ConfigService(config_dir)
    config.save_dataset_root(data_root)
    manager = DatasetManager(config)

    root_listing = manager.browse("")
    assert {d["name"] for d in root_listing["dirs"]} == {"level1"}
    assert root_listing["current"]["rel"] == ""
    assert root_listing["parent"]["rel"] == ""

    level1_listing = manager.browse("level1")
    assert {d["name"] for d in level1_listing["dirs"]} == {"level2", "sibling"}
    assert level1_listing["current"]["rel"] == "level1"
    assert level1_listing["parent"]["rel"] == ""

    level2_listing = manager.browse("level1/level2")
    assert level2_listing["dirs"] == []
    assert level2_listing["current"]["rel"] == "level1/level2"
    assert level2_listing["parent"]["rel"] == "level1"
