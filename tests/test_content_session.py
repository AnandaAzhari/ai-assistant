import tempfile
import unittest
from pathlib import Path

from app.content_session import ContentSessionStore


class ContentSessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = ContentSessionStore(self.db)

    def test_save_and_load_roundtrip(self):
        scope = self.store.build_scope("risol_mamqi", "instagram", "content-1")
        payload = {"version": 1, "stage": "draft_caption", "caption": "Risol anget nih!"}
        self.store.save(scope, payload)
        loaded = self.store.load(scope)
        self.assertEqual(loaded, payload)

    def test_load_missing_scope_returns_none(self):
        self.assertIsNone(self.store.load("risol_mamqi:instagram:tidak-ada"))

    def test_load_raises_on_unrecognized_version(self):
        scope = self.store.build_scope("pixiva_id", "tiktok", "content-2")
        self.store.save(scope, {"version": 2, "stage": "draft_caption"})
        with self.assertRaises(ValueError):
            self.store.load(scope)

    def test_save_overwrites_existing_scope(self):
        scope = self.store.build_scope("pixiva_id", "instagram", "content-3")
        self.store.save(scope, {"version": 1, "stage": "draft_caption"})
        self.store.save(scope, {"version": 1, "stage": "needs_review", "note": "revisi hook"})
        loaded = self.store.load(scope)
        self.assertEqual(loaded["stage"], "needs_review")
        self.assertEqual(loaded["note"], "revisi hook")

    def test_build_scope_joins_business_platform_content_id(self):
        scope = self.store.build_scope("taqi_desk", "whatsapp_status", "content-9")
        self.assertEqual(scope, "taqi_desk:whatsapp_status:content-9")

    def test_build_scope_rejects_empty_parts(self):
        with self.assertRaises(ValueError):
            self.store.build_scope("", "instagram", "content-1")
        with self.assertRaises(ValueError):
            self.store.build_scope("risol_mamqi", "", "content-1")
        with self.assertRaises(ValueError):
            self.store.build_scope("risol_mamqi", "instagram", "")

    def test_clear_removes_scope(self):
        scope = self.store.build_scope("risol_mamqi", "instagram", "content-4")
        self.store.save(scope, {"version": 1, "stage": "scheduled"})
        self.store.clear(scope)
        self.assertIsNone(self.store.load(scope))

    def test_clear_missing_scope_does_not_raise(self):
        self.store.clear("risol_mamqi:instagram:tidak-pernah-ada")

    def test_sessions_for_different_scopes_are_independent(self):
        scope_a = self.store.build_scope("risol_mamqi", "instagram", "content-1")
        scope_b = self.store.build_scope("pixiva_id", "instagram", "content-1")
        self.store.save(scope_a, {"version": 1, "stage": "draft_caption"})
        self.store.save(scope_b, {"version": 1, "stage": "scheduled"})
        self.assertEqual(self.store.load(scope_a)["stage"], "draft_caption")
        self.assertEqual(self.store.load(scope_b)["stage"], "scheduled")


if __name__ == "__main__":
    unittest.main()
