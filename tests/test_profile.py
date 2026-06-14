from pathlib import Path
import tempfile
import unittest

from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import load_profile, save_profile_key, save_shortcut


class ProfileTests(unittest.TestCase):
    def test_profile_round_trips_through_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory.sqlite3"
            store = WorkspaceMemoryStore(db_path)
            store.ensure_schema()
            save_profile_key(store, "tone", "terse")
            save_profile_key(store, "detail_level", "minimal")
            save_profile_key(store, "default_workspace", "adev")
            save_shortcut(store, "s", "/status")

            profile = load_profile(store)

        self.assertEqual("terse", profile.tone)
        self.assertEqual("minimal", profile.detail_level)
        self.assertEqual("adev", profile.default_workspace)
        self.assertEqual("/status", profile.shortcuts["s"])


if __name__ == "__main__":
    unittest.main()
