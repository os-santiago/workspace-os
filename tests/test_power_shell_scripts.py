from pathlib import Path
import tempfile
import unittest

import subprocess


class PowerShellScriptTests(unittest.TestCase):
    def test_wos_wrapper_defaults_to_shell_and_forwards_args(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "wos.ps1"
        rendered = script.read_text(encoding="utf-8")

        self.assertIn("python -m workspace_os", rendered)
        self.assertIn('config/workspace.sources.example.json', rendered)
        self.assertIn('"shell"', rendered)

    def test_install_script_adds_wos_function_to_profile(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "install-wos-command.ps1"
        rendered = script.read_text(encoding="utf-8")

        self.assertIn("function wos", rendered)
        self.assertIn("scripts/wos.ps1", rendered)
        self.assertIn("# Workspace OS command", rendered)
        self.assertIn("Add-UserPathEntry", rendered)
        self.assertIn("added_to_path=", rendered)

    def test_wos_wrapper_starts_workspace_next_action(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "wos.ps1"
        repo_root = script.parents[1]

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "next",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("Workspace next action:", result.stdout)

    def test_install_script_writes_wos_function_to_temp_profile(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "install-wos-command.ps1"
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f"& '{script}' -ProfilePath '{profile}'; if (-not (Test-Path '{profile}')) {{ exit 1 }}; Get-Content '{profile}'",
                ],
                cwd=script.parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
            rendered = result.stdout

        self.assertIn("function wos", rendered)
        self.assertIn("wos.ps1", rendered)

    def test_cmd_wrapper_forwards_to_powershell_launcher(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "wos.cmd"
        rendered = script.read_text(encoding="utf-8")

        self.assertIn("powershell -NoProfile -ExecutionPolicy Bypass -File", rendered)
        self.assertIn("%~dp0wos.ps1", rendered)


if __name__ == "__main__":
    unittest.main()
