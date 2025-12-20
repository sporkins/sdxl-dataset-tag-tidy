import unittest

from app.services.tag_service import TagService


class TagRulesEngineTests(unittest.TestCase):
    def test_parses_tags_into_categories(self):
        categories = TagService.categorize_tags([
            "Full Body",
            "from behind",
            "smile",
            "closed eyes",
            "arms crossed",
        ])

        self.assertIn("framing", categories)
        self.assertIn("view_angle", categories)
        self.assertIn("expression", categories)
        self.assertIn("eyes_state", categories)
        self.assertIn("arm_hand_position", categories)

    def test_face_gating_forbids_face_tags_from_behind(self):
        hints = TagService.compute_hints(["from behind", "smile", "looking at viewer"])

        self.assertIn("forbidden", hints)
        self.assertIn("smile", hints["forbidden"])
        self.assertIn("looking at viewer", hints["forbidden"])
        self.assertNotIn("expression", hints["missing_required"])

    def test_face_visible_requires_core_face_categories(self):
        hints = TagService.compute_hints(["front view"])

        for required in ["gaze", "expression", "mouth_state"]:
            self.assertIn(required, hints["missing_required"])

    def test_close_up_relaxes_view_and_pose(self):
        hints = TagService.compute_hints(
            ["close-up"],
            {"lower_body_and_ground_contact_visible": True},
        )

        self.assertNotIn("view_angle", hints["missing_required"])
        self.assertNotIn("pose", hints["missing_required"])
        self.assertIn("view_angle", hints["not_required"])
        self.assertIn("pose", hints["not_required"])

    def test_singleton_category_violation_flagged(self):
        hints = TagService.compute_hints(["smile", "frown"])

        self.assertIn("invalid", hints)
        self.assertIn("expression", hints["invalid"])

    def test_soft_category_allows_freeform(self):
        hints = TagService.compute_hints([
            "front view",
            "smile",
            "looking at viewer",
            "open mouth",
            "raised hand",
        ])

        self.assertNotIn("invalid", hints)
        self.assertEqual([], [item for item in hints["missing_required"] if item == "arm_hand_position"])

    def test_missing_framing_warns(self):
        hints = TagService.compute_hints([])

        self.assertIn("framing", hints["possibly_missing"])
        self.assertNotIn("framing", hints["missing_required"])

    def test_missing_framing_ignored_for_close_up(self):
        hints = TagService.compute_hints(["close-up"])

        self.assertNotIn("framing", hints["possibly_missing"])
        self.assertNotIn("framing", hints["missing_required"])

    def test_pose_missing_warns_when_lower_body_visible(self):
        hints = TagService.compute_hints([], {"lower_body_and_ground_contact_visible": True})

        self.assertIn("pose", hints["possibly_missing"])

    def test_pose_missing_relaxed_by_close_up(self):
        hints = TagService.compute_hints(
            ["close-up"], {"lower_body_and_ground_contact_visible": True}
        )

        self.assertNotIn("pose", hints["possibly_missing"])
        self.assertIn("pose", hints["not_required"])

    def test_identity_token_records_info(self):
        hints = TagService.compute_hints(["identity token"])

        self.assertIn("info", hints)
        self.assertIn("identity token", hints["info"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
