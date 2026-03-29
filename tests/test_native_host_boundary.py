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

    def test_vendored_portable_launcher_keeps_python_bridge_as_compatibility_boundary(self):
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

    def test_runtime_manifest_exists_and_describes_current_native_target(self):
        manifest = self.runtime_manifest.read_text(encoding="utf-8")
        self.assertIn('RUNTIME_KIND=native', manifest)
        self.assertIn('RUNTIME_BIN_REL=bin/kagi-native-runtime', manifest)
        self.assertIn('ENTRY_STYLE=direct', manifest)
        self.assertIn('ENTRY_TARGET=kagi.host_entry', manifest)
        self.assertIn('IMAGE_REL=app/kagi-canonical-image', manifest)
        self.assertIn('WORKSPACE_REL=workspace', manifest)

    def test_default_manifest_selects_native_canonical_image(self):
        manifest = self.runtime_manifest.read_text(encoding="utf-8")
        self.assertNotIn('RUNTIME_KIND=python', manifest)
        self.assertNotIn('RUNTIME_BIN_REL=bin/python3', manifest)
        self.assertNotIn('IMAGE_REL=app/kagi_app.zip', manifest)

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
        self.assertIn('selfhost_entries', source)
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

            frontend_copy = tmp_path / "frontend_copy.ks"
            frontend_copy.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            program_copy = tmp_path / "program_copy.ksrc"
            program_copy.write_text(
                (self.root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

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
                [str(launcher_bin), "selfhost-bootstrap", "--json", str(frontend_copy)],
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
                [str(launcher_bin), "selfhost-run", str(frontend_copy), str(program_copy)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello, world!\n")

    def test_built_launcher_can_execute_canonical_native_image_from_default_manifest(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_copy = tmp_path / "default_frontend_copy.ks"
            frontend_copy.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            program_copy = tmp_path / "default_program_copy.ksrc"
            program_copy.write_text(
                (self.root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(frontend_copy), str(program_copy)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello, world!\n")

    def test_default_manifest_native_image_supports_selfhost_json_commands(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            env = {**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""}
            frontend_copy = tmp_path / "frontend_json_alias.ks"
            frontend_copy.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            program_copy = tmp_path / "program_json_alias.ksrc"
            program_copy.write_text(
                (self.root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            frontend = str(frontend_copy)
            program = str(program_copy)

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", frontend, program],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            parse_payload = __import__("json").loads(parse.stdout)
            self.assertTrue(parse_payload["ok"])
            self.assertEqual(parse_payload["entry"], "parse")

            check = subprocess.run(
                [str(launcher_bin), "selfhost-check", "--json", frontend, program],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            check_payload = __import__("json").loads(check.stdout)
            self.assertTrue(check_payload["ok"])
            self.assertEqual(check_payload["value"], "ok")
            self.assertEqual(check_payload["effects"]["program"], ["print"])

            emit = subprocess.run(
                [str(launcher_bin), "selfhost-emit", frontend, program],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(emit.returncode, 0, emit.stderr)
            emit_payload = __import__("json").loads(emit.stdout)
            self.assertTrue(emit_payload["ok"])
            self.assertIn("print_many", emit_payload["artifact"])

            capir = subprocess.run(
                [str(launcher_bin), "selfhost-capir", frontend, program],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(capir.returncode, 0, capir.stderr)
            capir_payload = __import__("json").loads(capir.stdout)
            self.assertTrue(capir_payload["ok"])
            self.assertEqual(capir_payload["capir"]["effect"], "print")

            run_json = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", frontend, program],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(run_json.returncode, 0, run_json.stderr)
            run_payload = __import__("json").loads(run_json.stdout)
            self.assertTrue(run_payload["ok"])
            self.assertEqual(run_payload["value"], "hello, world!\n")

    def test_default_manifest_native_image_accepts_frontend_kir_and_whitespace_variant_program(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_kir_path = tmp_path / "frontend.kir.json"
            frontend_kir_path.write_text(
                (self.root / "examples" / "selfhost_frontend.kir.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            variant_program = tmp_path / "variant.ksrc"
            variant_program.write_text(
                'fn emit_suffix(name){print concat(name,"!")}\n\ncall emit_suffix("hello, world")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(frontend_kir_path), str(variant_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello, world!\n")

    def test_default_manifest_native_image_accepts_whitespace_variant_frontend_source(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_variant = tmp_path / "frontend_variant.ks"
            frontend_variant.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8").replace("\n", "\n\n"),
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-build", "--json", str(frontend_variant)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["fixed_point"])

    def test_default_manifest_native_image_accepts_frontend_kir_alias_for_selfhost_freeze_json(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_kir_alias = tmp_path / "frontend_alias.kir.json"
            frontend_kir_alias.write_text(
                (self.root / "examples" / "selfhost_frontend.kir.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-freeze", "--json", str(frontend_kir_alias)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["kir"]["kind"], "kir")

    def test_default_manifest_native_image_accepts_whitespace_frontend_and_identifier_renamed_program_json(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_variant = tmp_path / "frontend_variant.ks"
            frontend_variant.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8").replace("\n", "\n\n"),
                encoding="utf-8",
            )
            variant_program = tmp_path / "renamed_json.ksrc"
            variant_program.write_text(
                'fn shout(x) {\n'
                '  print concat(x, "!")\n'
                '}\n\n'
                'call shout("hello, world")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(frontend_variant), str(variant_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["value"], "hello, world!\n")

    def test_default_manifest_native_image_accepts_identifier_renamed_variant_program(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            variant_program = tmp_path / "renamed.ksrc"
            variant_program.write_text(
                'fn shout(x) {\n'
                '  print concat(x, "!")\n'
                '}\n\n'
                'call shout("hello, world")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(variant_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello, world!\n")

    @unittest.expectedFailure
    def test_future_line_parser_native_image_can_parse_noncanonical_single_print_program(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_copy = tmp_path / "frontend_alias.ks"
            frontend_copy.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            variant_program = tmp_path / "future_single_print.ksrc"
            variant_program.write_text(
                'print "hello from future native parser"\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(frontend_copy), str(variant_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )

            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["entry"], "parse")
            self.assertEqual(
                __import__("json").loads(payload["ast"]),
                {
                    "kind": "program",
                    "functions": [],
                    "statements": [
                        {
                            "kind": "print",
                            "expr": {
                                "kind": "string",
                                "value": "hello from future native parser",
                            },
                        }
                    ],
                },
            )

    @unittest.expectedFailure
    def test_future_line_parser_native_image_can_run_noncanonical_let_concat_program(self):
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

            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            frontend_copy = tmp_path / "frontend_alias.ks"
            frontend_copy.write_text(
                (self.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            variant_program = tmp_path / "future_let_concat.ksrc"
            variant_program.write_text(
                'let greeting = concat("native ", "parser future")\n'
                'print greeting\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(frontend_copy), str(variant_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )

            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["value"], "native parser future\n")
            self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["native parser future"]}')

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(variant_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            self.assertIn('"name":"shout"', payload["ast"])
            self.assertIn('"params":["x"]', payload["ast"])


if __name__ == "__main__":
    unittest.main()
