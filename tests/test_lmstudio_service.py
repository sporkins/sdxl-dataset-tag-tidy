import pytest

from app.services.lmstudio_service import LmStudioInvalidResponseError, LmStudioService


def test_parse_first_line_tags_basic():
    output = "tag1, TAG2, tag1, extra-info\nmore text"
    tags = LmStudioService.parse_first_line_tags(output)
    assert tags == ["tag1", "tag2", "extra-info"]


def test_parse_first_line_tags_rejects_invalid_tokens():
    output = "good, bad!, another"
    with pytest.raises(LmStudioInvalidResponseError):
        LmStudioService.parse_first_line_tags(output)


def test_parse_first_line_tags_applies_exclusions_and_trimming():
    output = " keep , DROP , drop,New "
    tags = LmStudioService.parse_first_line_tags(output, exclusions=["drop"])
    assert tags == ["keep", "new"]
