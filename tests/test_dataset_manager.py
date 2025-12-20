from app.models import FilterCriteria, ImageData
from app.services.config_service import ConfigService
from app.services.dataset_manager import DatasetManager


def _dummy_manager(tmp_path):
    config_dir = tmp_path / "config"
    config = ConfigService(config_dir)
    return DatasetManager(config)


def test_browse_allows_multi_level_navigation(tmp_path):
    config = ConfigService(tmp_path / "config")
    data_root = tmp_path / "data"
    (data_root / "level1" / "level2").mkdir(parents=True)
    (data_root / "level1" / "sibling").mkdir()

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


def test_stage_image_edit_updates_tag(tmp_path):
    manager = _dummy_manager(tmp_path)
    img_path = tmp_path / "data" / "img.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img_path.write_bytes(b"")

    manager.images["img1"] = ImageData(
        image_id="img1",
        rel_path="img.png",
        abs_path=img_path,
        tags_original=["a", "b"],
        tags_current=["a", "b"],
    )

    result = manager.stage_image_edit("img1", {"type": "edit", "index": 1, "old_tag": "b", "new_tag": "c"})

    assert manager.images["img1"].tags_current == ["a", "c"]
    assert result["is_dirty"] is True


def test_complete_flag_hides_missing_required_in_filter(tmp_path):
    manager = _dummy_manager(tmp_path)
    img_path = tmp_path / "data" / "img.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img_path.write_bytes(b"")

    manager.images["img1"] = ImageData(
        image_id="img1",
        rel_path="img.png",
        abs_path=img_path,
        tags_original=[],
        tags_current=[],
    )

    filters = FilterCriteria(has_missing_required=True)
    initial = list(manager._filtered_images(filters))
    assert len(initial) == 1
    assert initial[0].image_id == "img1"

    manager.set_image_complete("img1", True)
    assert list(manager._filtered_images(filters)) == []

    manager.set_image_complete("img1", False)
    filtered = list(manager._filtered_images(filters))
    assert len(filtered) == 1
    assert filtered[0].image_id == "img1"
