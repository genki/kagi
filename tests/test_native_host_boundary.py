from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class NativeHostBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.launcher_source = cls.root / "portable" / "launcher" / "kagi_launcher.c"
        cls.build_script = cls.root / "portable" / "launcher" / "build.sh"
        cls.runtime_manifest = cls.root / "portable" / "launcher" / "kagi_runtime.env"
        cls.native_runtime_source = cls.root / "portable" / "runtime" / "kagi_native_runtime.c"
        cls.native_runtime_build_script = cls.root / "portable" / "runtime" / "build.sh"
        cls.native_image_source = cls.root / "portable" / "image" / "kagi_canonical_image.c"
        cls.native_image_build_script = cls.root / "portable" / "image" / "build.sh"

    def test_vendored_portable_launcher_source_exists(self):
        self.assertTrue(self.launcher_source.exists())

    def test_vendored_portable_launcher_captures_current_cpython_host_boundary(self):
        source = self.launcher_source.read_text(encoding="utf-8")
        self.assertIn('kagi_runtime.env', source)
        self.assertIn('RUNTIME_KIND', source)
        self.assertIn('RUNTIME_BIN_REL', source)
        self.assertIn('ENTRY_STYLE', source)
        self.assertIn('ENTRY_TARGET', source)
        self.assertIn('IMAGE_REL', source)
        self.assertIn('WORKSPACE_REL', source)
        self.assertIn('PYTHONHOME', source)
        self.assertIn('PYTHONPATH', source)
        self.assertIn('KAGI_HOME', source)
        self.assertIn('"failed to exec bundled python: %s\\n"', source)

    def test_launcher_build_script_exists_and_targets_vendored_source(self):
        script = self.build_script.read_text(encoding="utf-8")
        self.assertIn('kagi_launcher.c', script)
        self.assertIn('cc -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -std=c11', script)

    def test_runtime_manifest_exists_and_describes_current_host_target(self):
        manifest = self.runtime_manifest.read_text(encoding="utf-8")
        self.assertIn('RUNTIME_KIND=python', manifest)
        self.assertIn('RUNTIME_BIN_REL=bin/python3', manifest)
        self.assertIn('ENTRY_STYLE=python-module', manifest)
        self.assertIn('ENTRY_TARGET=kagi.host_entry', manifest)
        self.assertIn('IMAGE_REL=app/kagi_app.zip', manifest)
        self.assertIn('WORKSPACE_REL=workspace', manifest)

    def test_launcher_source_supports_native_direct_runtime_kind(self):
        source = self.launcher_source.read_text(encoding="utf-8")
        self.assertIn('strcmp(manifest.runtime_kind, "native") == 0', source)
        self.assertIn('strcmp(manifest.entry_style, "direct") != 0', source)
        self.assertIn('KAGI_IMAGE', source)
        self.assertIn('KAGI_ENTRY_TARGET', source)
        self.assertIn('failed to exec native runtime', source)

    def test_native_runtime_bridge_source_exists(self):
        source = self.native_runtime_source.read_text(encoding="utf-8")
        self.assertIn('missing KAGI_IMAGE', source)
        self.assertIn('missing KAGI_HOME', source)
        self.assertIn('failed to exec native image', source)
        self.assertIn('failed to exec native bridge python', source)
        self.assertIn('bin/python3', source)
        self.assertIn('"-m"', source)

    def test_native_image_source_exists(self):
        source = self.native_image_source.read_text(encoding="utf-8")
        self.assertIn('selfhost-bootstrap', source)
        self.assertIn('selfhost-build', source)
        self.assertIn('selfhost-freeze', source)
        self.assertIn('selfhost-run', source)
        self.assertIn('selfhost_bundles', source)
        self.assertIn('canonical-seed-kir', source)

    def test_built_launcher_can_execute_native_runtime_bridge_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace" / "src").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run(
                [str(self.build_script), str(launcher_bin)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run(
                [str(self.native_runtime_build_script), str(native_runtime_bin)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            python_wrapper = dist / "bin" / "python3"
            python_wrapper.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "exec /usr/bin/python3 \"$@\"\n",
                encoding="utf-8",
            )
            python_wrapper.chmod(0o755)

            shutil.copytree(self.root / "src" / "kagi", dist / "workspace" / "src" / "kagi")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            (dist / "app" / "kagi_runtime.env").write_text(
                "RUNTIME_KIND=native\n"
                "RUNTIME_BIN_REL=bin/kagi-native-runtime\n"
                "ENTRY_STYLE=direct\n"
                "ENTRY_TARGET=kagi.host_entry\n"
                "IMAGE_REL=workspace/src\n"
                "WORKSPACE_REL=workspace\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [str(launcher_bin), "selfhost-bootstrap", "--json", str(self.root / "examples" / "selfhost_frontend.ks")],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = __import__("json").loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["seed_kind"], "canonical-seed-kir")

    def test_native_runtime_bridge_can_exec_direct_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run(
                [str(self.native_runtime_build_script), str(native_runtime_bin)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            direct_image = dist / "app" / "direct-image"
            direct_image.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'entry=%s\\n' \"$1\"\n"
                "printf 'home=%s\\n' \"$KAGI_HOME\"\n"
                "shift\n"
                "printf 'args=%s\\n' \"$*\"\n",
                encoding="utf-8",
            )
            direct_image.chmod(0o755)

            completed = subprocess.run(
                [str(native_runtime_bin), "selfhost.bootstrap", "--json", "hello.ks"],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "KAGI_IMAGE": str(direct_image),
                    "KAGI_HOME": str(dist / "workspace"),
                    "PYTHONHOME": "",
                    "PYTHONPATH": "",
                },
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("entry=selfhost.bootstrap", completed.stdout)
            self.assertIn(f"home={dist / 'workspace'}", completed.stdout)
            self.assertIn("args=--json hello.ks", completed.stdout)

    def test_built_launcher_can_execute_canonical_native_image_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run(
                [str(self.build_script), str(launcher_bin)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run(
                [str(self.native_runtime_build_script), str(native_runtime_bin)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run(
                [str(self.native_image_build_script), str(native_image_bin)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            (dist / "app" / "kagi_runtime.env").write_text(
                "RUNTIME_KIND=native\n"
                "RUNTIME_BIN_REL=bin/kagi-native-runtime\n"
                "ENTRY_STYLE=direct\n"
                "ENTRY_TARGET=kagi.host_entry\n"
                "IMAGE_REL=app/kagi-canonical-image\n"
                "WORKSPACE_REL=workspace\n",
                encoding="utf-8",
            )

            bootstrap = subprocess.run(
                [str(launcher_bin), "selfhost-bootstrap", "--json", str(self.root / "examples" / "selfhost_frontend.ks")],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
            payload = __import__("json").loads(bootstrap.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["seed_kind"], "canonical-seed-kir")

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(self.root / "examples" / "hello_arg_fn.ksrc")],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello, world!\n")


if __name__ == "__main__":
    unittest.main()
