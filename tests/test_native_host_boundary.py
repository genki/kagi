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
        cls.native_image_output_source = cls.root / "portable" / "image" / "kagi_image_output.c"
        cls.native_image_parser_source = cls.root / "portable" / "image" / "kagi_image_parser.c"
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
        self.assertIn('#include "kagi_image_output.h"', source)
        self.assertIn('#include "kagi_image_parser.h"', source)
        self.assertIn('is_selfhost_fixed_point_command(command)', source)
        self.assertIn('emit_native_selfhost_command(', source)
        self.assertIn('try_parse_native_function_program', source)
        self.assertIn('try_parse_native_stmt_program', source)
        self.assertNotIn('match_canonical_case', source)
        self.assertNotIn('rewrite_snapshot_identifiers', source)

    def test_native_image_output_source_exists(self):
        source = self.native_image_output_source.read_text(encoding="utf-8")
        self.assertIn('canonical-seed-kir', source)
        self.assertIn('emit_selfhost_bootstrap_json', source)
        self.assertIn('emit_native_selfhost_command', source)
        self.assertIn('unsupported_source', source)

    def test_native_image_parser_source_exists(self):
        source = self.native_image_parser_source.read_text(encoding="utf-8")
        self.assertIn('normalized_source_equals', source)
        self.assertIn('try_parse_native_stmt_program', source)
        self.assertIn('try_parse_native_function_program', source)
        self.assertIn('free_native_function_program', source)

    def test_native_image_build_script_compiles_split_sources(self):
        script = self.native_image_build_script.read_text(encoding="utf-8")
        self.assertIn('kagi_canonical_image.c', script)
        self.assertIn('kagi_image_output.c', script)
        self.assertIn('kagi_image_parser.c', script)

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

    def test_selfhost_freeze_kir_alias_does_not_need_canonical_frontend_source_file(self):
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
            os.remove(dist / "workspace" / "examples" / "selfhost_frontend.ks")

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

    def test_selfhost_build_kir_alias_does_not_need_canonical_frontend_source_file(self):
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
            os.remove(dist / "workspace" / "examples" / "selfhost_frontend.ks")

            frontend_kir_alias = tmp_path / "frontend_alias.kir.json"
            frontend_kir_alias.write_text(
                (self.root / "examples" / "selfhost_frontend.kir.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-build", "--json", str(frontend_kir_alias)],
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

    def test_selfhost_bootstrap_kir_alias_does_not_need_canonical_frontend_source_file(self):
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
            os.remove(dist / "workspace" / "examples" / "selfhost_frontend.ks")

            frontend_kir_alias = tmp_path / "frontend_alias.kir.json"
            frontend_kir_alias.write_text(
                (self.root / "examples" / "selfhost_frontend.kir.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-bootstrap", "--json", str(frontend_kir_alias)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["seed_kind"], "canonical-seed-kir")

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

    def test_native_image_can_parse_noncanonical_single_print_program(self):
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

    def test_future_line_parser_native_image_can_parse_renamed_hello_arg_fn_shape(self):
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
            renamed_program = tmp_path / "renamed_hello_arg_fn.ksrc"
            renamed_program.write_text(
                'fn shout(x) {\n'
                '  print concat(x, "!")\n'
                '}\n\n'
                'call shout("hello, world")\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(frontend_copy), str(renamed_program)],
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
                    "functions": [
                        {
                            "kind": "fn",
                            "name": "shout",
                            "params": ["x"],
                            "body": [
                                {
                                    "kind": "print",
                                    "expr": {
                                        "kind": "concat",
                                        "left": {"kind": "var", "name": "x"},
                                        "right": {"kind": "string", "value": "!"},
                                    },
                                }
                            ],
                        }
                    ],
                    "statements": [
                        {
                            "kind": "call",
                            "name": "shout",
                            "args": [{"kind": "string", "value": "hello, world"}],
                        }
                    ],
                },
            )

    def test_future_line_parser_native_image_can_parse_nested_function_body_shape(self):
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
            nested_program = tmp_path / "nested_function_shape.ksrc"
            nested_program.write_text(
                'fn choose(name) {\n'
                '  let ready = eq(name, "go")\n'
                '  if ready {\n'
                '    print concat(name, "!")\n'
                '  } else {\n'
                '    print "disabled"\n'
                '  }\n'
                '}\n\n'
                'call choose("go")\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(frontend_copy), str(nested_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )

            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(
                __import__("json").loads(payload["ast"]),
                {
                    "kind": "program",
                    "functions": [
                        {
                            "kind": "fn",
                            "name": "choose",
                            "params": ["name"],
                            "body": [
                                {
                                    "kind": "let",
                                    "name": "ready",
                                    "expr": {
                                        "kind": "eq",
                                        "left": {"kind": "var", "name": "name"},
                                        "right": {"kind": "string", "value": "go"},
                                    },
                                },
                                {
                                    "kind": "if_stmt",
                                    "condition": {"kind": "var", "name": "ready"},
                                    "then_body": [
                                        {
                                            "kind": "print",
                                            "expr": {
                                                "kind": "concat",
                                                "left": {"kind": "var", "name": "name"},
                                                "right": {"kind": "string", "value": "!"},
                                            },
                                        }
                                    ],
                                    "else_body": [
                                        {
                                            "kind": "print",
                                            "expr": {"kind": "string", "value": "disabled"},
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                    "statements": [
                        {
                            "kind": "call",
                            "name": "choose",
                            "args": [{"kind": "string", "value": "go"}],
                        }
                    ],
                },
            )

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
            self.assertEqual(
                __import__("json").loads(payload["ast"]),
                {
                    "kind": "program",
                    "functions": [],
                    "statements": [
                        {
                            "kind": "let",
                            "name": "greeting",
                            "expr": {
                                "kind": "concat",
                                "left": {"kind": "string", "value": "native "},
                                "right": {"kind": "string", "value": "parser future"},
                            },
                        },
                        {
                            "kind": "print",
                            "expr": {"kind": "var", "name": "greeting"},
                        },
                    ],
                },
            )

    def test_future_line_parser_native_image_can_parse_noncanonical_let_print_program(self):
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
            let_print_program = tmp_path / "future_let_print.ksrc"
            let_print_program.write_text(
                'let greeting = "hello from let print"\n'
                'print greeting\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(frontend_copy), str(let_print_program)],
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
                            "kind": "let",
                            "name": "greeting",
                            "expr": {
                                "kind": "string",
                                "value": "hello from let print",
                            },
                        },
                        {
                            "kind": "print",
                            "expr": {
                                "kind": "var",
                                "name": "greeting",
                            },
                        },
                    ],
                },
            )

    def test_future_line_parser_native_image_can_parse_noncanonical_zero_arg_fn_call_program(self):
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
            zero_arg_program = tmp_path / "future_zero_arg_fn.ksrc"
            zero_arg_program.write_text(
                'fn greet() {\n'
                '  print "hello from zero arg"\n'
                '}\n\n'
                'call greet()\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(frontend_copy), str(zero_arg_program)],
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
                    "functions": [
                        {
                            "kind": "fn",
                            "name": "greet",
                            "params": [],
                            "body": [
                                {
                                    "kind": "print",
                                    "expr": {
                                        "kind": "string",
                                        "value": "hello from zero arg",
                                    },
                                }
                            ],
                        }
                    ],
                    "statements": [
                        {
                            "kind": "call",
                            "name": "greet",
                            "args": [],
                        }
                    ],
                },
            )

    def test_future_line_parser_native_image_can_run_noncanonical_zero_arg_fn_call_program(self):
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
            zero_arg_program = tmp_path / "future_zero_arg_fn.ksrc"
            zero_arg_program.write_text(
                'fn greet() {\n'
                '  print "hello from zero arg"\n'
                '}\n\n'
                'call greet()\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(frontend_copy), str(zero_arg_program)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )

            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["value"], "hello from zero arg\n")
            self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello from zero arg"]}')

    def test_default_manifest_native_image_synthesizes_noncanonical_print_only_program(self):
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

            source_path = tmp_path / "print_only.ksrc"
            source_path.write_text(
                'print "alpha"\nprint concat("be", "ta")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "alpha\nbeta\n")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            parse_payload = __import__("json").loads(parse.stdout)
            self.assertIn('"value":"alpha"', parse_payload["ast"])
            self.assertIn('"kind":"concat"', parse_payload["ast"])

    def test_default_manifest_native_image_synthesizes_noncanonical_let_print_program(self):
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

            source_path = tmp_path / "let_print.ksrc"
            source_path.write_text(
                'let message = concat("ga", "mma")\nprint message\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "gamma\n")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            parse_payload = __import__("json").loads(parse.stdout)
            self.assertIn('"kind":"let"', parse_payload["ast"])
            self.assertIn('"name":"message"', parse_payload["ast"])

    def test_default_manifest_native_image_synthesizes_noncanonical_if_expr_program(self):
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

            source_path = tmp_path / "if_expr.ksrc"
            source_path.write_text(
                'let greeting = concat("he", "llo")\n'
                'let enabled = eq(greeting, "hello")\n'
                'print if(enabled, greeting, "disabled")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello\n")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(payload["ast"])
            self.assertEqual(ast["statements"][2]["kind"], "print")
            self.assertEqual(ast["statements"][2]["expr"]["kind"], "if")

    def test_default_manifest_native_image_synthesizes_renamed_if_expr_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "if_expr_renamed.ksrc"
            source_path.write_text(
                'let message = concat("native ", "expr")\n'
                'let ok = eq(message, "native expr")\n'
                'print if(ok, message, "disabled")\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(payload["ast"])
            self.assertEqual(ast["statements"][0]["name"], "message")
            self.assertEqual(ast["statements"][1]["name"], "ok")
            self.assertEqual(ast["statements"][2]["expr"]["condition"]["name"], "ok")
            self.assertEqual(ast["statements"][2]["expr"]["then"]["name"], "message")

    def test_default_manifest_native_image_runs_false_branch_if_expr_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "if_expr_false.ksrc"
            source_path.write_text(
                'let message = "native expr"\n'
                'let ok = eq(message, "mismatch")\n'
                'print if(ok, message, "disabled")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "disabled\n")
            self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["disabled"]}')

    def test_default_manifest_native_image_synthesizes_noncanonical_if_stmt_program(self):
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

            source_path = tmp_path / "if_stmt.ksrc"
            source_path.write_text(
                'let greeting = concat("he", "llo")\n'
                'let enabled = eq(greeting, "hello")\n'
                'if enabled {\n'
                '  print greeting\n'
                '} else {\n'
                '  print "disabled"\n'
                '}\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "hello\n")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(payload["ast"])
            self.assertEqual(ast["statements"][2]["kind"], "if_stmt")

    def test_default_manifest_native_image_synthesizes_renamed_if_stmt_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "if_stmt_renamed.ksrc"
            source_path.write_text(
                'let message = concat("native ", "stmt")\n'
                'let ready = eq(message, "native stmt")\n'
                'if ready {\n'
                '  print message\n'
                '} else {\n'
                '  print "disabled"\n'
                '}\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(payload["ast"])
            self.assertEqual(ast["statements"][0]["name"], "message")
            self.assertEqual(ast["statements"][1]["name"], "ready")
            self.assertEqual(ast["statements"][2]["condition"]["name"], "ready")
            self.assertEqual(ast["statements"][2]["then_body"][0]["expr"]["name"], "message")

    def test_default_manifest_native_image_runs_false_branch_if_stmt_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "if_stmt_false.ksrc"
            source_path.write_text(
                'let message = "native stmt"\n'
                'let ready = eq(message, "mismatch")\n'
                'if ready {\n'
                '  print message\n'
                '} else {\n'
                '  print "disabled"\n'
                '}\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "disabled\n")
            self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["disabled"]}')

    def test_default_manifest_native_image_synthesizes_mixed_top_level_stmt_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "mixed_stmt.ksrc"
            source_path.write_text(
                'let prefix = "alpha"\n'
                'print prefix\n'
                'print concat("be", "ta")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "alpha\nbeta\n")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(payload["ast"])
            self.assertEqual(len(ast["statements"]), 3)
            self.assertEqual(ast["statements"][0]["kind"], "let")
            self.assertEqual(ast["statements"][1]["kind"], "print")
            self.assertEqual(ast["statements"][2]["kind"], "print")

    def test_future_generic_function_parser_handles_mixed_functions_and_top_level_statements(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "mixed_fn_stmt.ksrc"
            source_path.write_text(
                'fn greet() {\n'
                '  print "alpha"\n'
                '}\n\n'
                'call greet()\n'
                'print concat("be", "ta")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "alpha\nbeta\n")
            self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["alpha","beta"]}')

    def test_future_generic_function_parser_preserves_renamed_single_arg_function_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "renamed_single_arg.ksrc"
            source_path.write_text(
                'fn shout(text) {\n'
                '  print concat(text, "!")\n'
                '}\n\n'
                'call shout("hello")\n',
                encoding="utf-8",
            )

            capir = subprocess.run(
                [str(launcher_bin), "selfhost-capir", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(capir.returncode, 0, capir.stderr)
            payload = __import__("json").loads(capir.stdout)
            kir = payload["kir"]
            self.assertEqual(kir["functions"][0]["name"], "shout")
            self.assertEqual(kir["functions"][0]["params"], ["text"])
            self.assertEqual(kir["instructions"][0]["name"], "shout")

    def test_future_generic_function_parser_handles_false_branch_inside_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            source_path = tmp_path / "fn_false_branch.ksrc"
            source_path.write_text(
                'fn choose() {\n'
                '  let ok = eq("a", "b")\n'
                '  if ok {\n'
                '    print concat("ba", "d")\n'
                '  } else {\n'
                '    print concat("go", "od")\n'
                '  }\n'
                '}\n\n'
                'call choose()\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "good\n")
            self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["good"]}')

    def test_generic_stmt_native_path_does_not_need_selfhost_entries_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")
            shutil.rmtree(dist / "workspace" / "examples" / "selfhost_entries")

            source_path = tmp_path / "generic_stmt.ksrc"
            source_path.write_text(
                'let message = concat("al", "pha")\n'
                'print message\n'
                'print concat("be", "ta")\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "alpha\nbeta\n")

    def test_exact_canonical_if_stmt_source_does_not_need_selfhost_entries_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")
            shutil.rmtree(dist / "workspace" / "examples" / "selfhost_entries")

            source_path = tmp_path / "hello_if_stmt_copy.ksrc"
            source_path.write_text((self.root / "examples" / "hello_if_stmt.ksrc").read_text(encoding="utf-8"), encoding="utf-8")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            parse_payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(parse_payload["ast"])
            self.assertEqual(ast["statements"][2]["kind"], "if_stmt")

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = __import__("json").loads(run.stdout)
            self.assertEqual(run_payload["value"], "hello, world!\n")

    def test_minified_if_stmt_variant_is_snapshotless(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")
            shutil.rmtree(dist / "workspace" / "examples" / "selfhost_entries")

            source_path = tmp_path / "if_stmt_minified.ksrc"
            source_path.write_text(
                'let greeting = "hello, world!"\n'
                'let enabled = eq(greeting, "hello, world!")\n'
                'if enabled{\n'
                'print greeting\n'
                '}else{\n'
                'print "disabled"\n'
                '}\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "hello, world!\n")

    def test_minified_function_header_and_expr_spacing_is_snapshotless(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")
            shutil.rmtree(dist / "workspace" / "examples" / "selfhost_entries")

            source_path = tmp_path / "function_minified.ksrc"
            source_path.write_text(
                'fn shout(text){\n'
                'print concat ( text , "!" )\n'
                '}\n'
                'call shout("hello")\n',
                encoding="utf-8",
            )

            capir = subprocess.run(
                [str(launcher_bin), "selfhost-capir", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(capir.returncode, 0, capir.stderr)
            payload = __import__("json").loads(capir.stdout)
            kir = payload["kir"]
            if isinstance(kir, str):
                kir = __import__("json").loads(kir)
            self.assertEqual(kir["functions"][0]["name"], "shout")
            self.assertEqual(kir["instructions"][0]["name"], "shout")

    def test_exact_canonical_corpus_runs_without_selfhost_entries_snapshots(self):
        corpus = {
            "hello.ksrc": "hello, world!\n",
            "hello_concat.ksrc": "hello, world!\n",
            "hello_print_concat.ksrc": "hello, world!\n",
            "hello_twice.ksrc": "hello\nworld\n",
            "hello_let.ksrc": "hello, world!\n",
            "hello_let_string.ksrc": "hello, world!\n",
            "hello_let_concat.ksrc": "hello, world!\n",
            "hello_if.ksrc": "hello, world!\n",
            "hello_if_stmt.ksrc": "hello, world!\n",
            "hello_fn.ksrc": "hello, world!\n",
            "hello_arg_fn.ksrc": "hello, world!\n",
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")
            shutil.rmtree(dist / "workspace" / "examples" / "selfhost_entries")

            for source_name, expected in corpus.items():
                source_path = tmp_path / f"copy_{source_name}"
                source_path.write_text((self.root / "examples" / source_name).read_text(encoding="utf-8"), encoding="utf-8")
                run = subprocess.run(
                    [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                    cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
                )
                self.assertEqual(run.returncode, 0, f"{source_name}: {run.stderr}")
                payload = __import__("json").loads(run.stdout)
                self.assertEqual(payload["value"], expected, source_name)

    def test_exact_canonical_if_expr_ignores_poisoned_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            entries = dist / "workspace" / "examples" / "selfhost_entries"
            (entries / "hello_if.parse.txt").write_text('"poison"\n', encoding="utf-8")
            (entries / "hello_if.compile.txt").write_text('{"kind":"pipeline","stdout":"poison","artifact":"\\"poison\\""}\n', encoding="utf-8")

            source_path = tmp_path / "hello_if_copy.ksrc"
            source_path.write_text((self.root / "examples" / "hello_if.ksrc").read_text(encoding="utf-8"), encoding="utf-8")

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            parse_payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(parse_payload["ast"])
            self.assertEqual(ast["statements"][2]["kind"], "print")
            self.assertNotEqual(parse_payload["ast"], '"poison"')

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = __import__("json").loads(run.stdout)
            self.assertEqual(run_payload["value"], "hello, world!\n")
            self.assertNotIn("poison", run.stdout)

    def test_exact_canonical_arg_fn_ignores_poisoned_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            entries = dist / "workspace" / "examples" / "selfhost_entries"
            (entries / "hello_arg_fn.kir.txt").write_text('{"kind":"kir","functions":[{"name":"poison","params":[],"body":[]}],"instructions":[]}\n', encoding="utf-8")
            (entries / "hello_arg_fn.analysis.txt").write_text('{"kind":"analysis_v1","function_arities":{"poison":0},"effects":{"program":[],"functions":{"poison":[]}}}\n', encoding="utf-8")
            (entries / "hello_arg_fn.compile.txt").write_text('{"kind":"pipeline","stdout":"poison","artifact":"\\"poison\\""}\n', encoding="utf-8")

            source_path = tmp_path / "hello_arg_fn_copy.ksrc"
            source_path.write_text((self.root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8"), encoding="utf-8")

            capir = subprocess.run(
                [str(launcher_bin), "selfhost-capir", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(capir.returncode, 0, capir.stderr)
            capir_payload = __import__("json").loads(capir.stdout)
            kir = capir_payload["kir"]
            if isinstance(kir, str):
                kir = __import__("json").loads(kir)
            self.assertEqual(kir["functions"][0]["name"], "emit_suffix")
            self.assertNotIn("poison", capir.stdout)

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = __import__("json").loads(run.stdout)
            self.assertEqual(run_payload["value"], "hello, world!\n")

    def test_generic_function_native_path_does_not_need_selfhost_entries_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")
            shutil.rmtree(dist / "workspace" / "examples" / "selfhost_entries")

            source_path = tmp_path / "generic_fn.ksrc"
            source_path.write_text(
                'fn shout(name) {\n'
                '  print concat(name, "!")\n'
                '}\n\n'
                'call shout("hello")\n'
                'print "tail"\n',
                encoding="utf-8",
            )

            run = subprocess.run(
                [str(launcher_bin), "selfhost-run", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = __import__("json").loads(run.stdout)
            self.assertEqual(payload["value"], "hello!\ntail\n")

    def test_generic_stmt_parse_ignores_poisoned_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            entries = dist / "workspace" / "examples" / "selfhost_entries"
            (entries / "hello_let.compile.txt").write_text("{\"kind\":\"pipeline\",\"ast\":\"\\\"poison\\\"\",\"hir\":\"\\\"poison\\\"\",\"kir\":\"\\\"poison\\\"\",\"analysis\":\"\\\"poison\\\"\",\"artifact\":\"\\\"poison\\\"\",\"stdout\":\"poison\",\"entry\":\"pipeline\",\"version\":\"v1\"}\n", encoding="utf-8")
            (entries / "hello_let.parse.txt").write_text("\"poison\"\n", encoding="utf-8")

            source_path = tmp_path / "generic_stmt.ksrc"
            source_path.write_text(
                'let message = concat("al", "pha")\n'
                'print message\n'
                'print concat("be", "ta")\n',
                encoding="utf-8",
            )

            parse = subprocess.run(
                [str(launcher_bin), "selfhost-parse", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(parse.returncode, 0, parse.stderr)
            payload = __import__("json").loads(parse.stdout)
            ast = __import__("json").loads(payload["ast"])
            self.assertEqual(ast["statements"][0]["name"], "message")
            self.assertEqual(ast["statements"][2]["expr"]["kind"], "concat")
            self.assertNotEqual(payload["ast"], '"poison"')

            check = subprocess.run(
                [str(launcher_bin), "selfhost-check", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            check_payload = __import__("json").loads(check.stdout)
            self.assertEqual(check_payload["effects"]["program"], ["print"])
            self.assertEqual(check_payload["value"], "ok")

    def test_generic_function_payloads_ignore_poisoned_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            (dist / "bin").mkdir(parents=True)
            (dist / "app").mkdir(parents=True)
            (dist / "workspace").mkdir(parents=True)

            launcher_bin = dist / "bin" / "kagi"
            subprocess.run([str(self.build_script), str(launcher_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_runtime_bin = dist / "bin" / "kagi-native-runtime"
            subprocess.run([str(self.native_runtime_build_script), str(native_runtime_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            native_image_bin = dist / "app" / "kagi-canonical-image"
            subprocess.run([str(self.native_image_build_script), str(native_image_bin)], cwd=self.root, check=True, capture_output=True, text=True)
            shutil.copy2(self.runtime_manifest, dist / "app" / "kagi_runtime.env")
            shutil.copytree(self.root / "examples", dist / "workspace" / "examples")

            entries = dist / "workspace" / "examples" / "selfhost_entries"
            (entries / "hello_arg_fn.kir.txt").write_text("{\"kind\":\"kir\",\"functions\":[{\"name\":\"poison\",\"params\":[],\"body\":[]}],\"instructions\":[]}\n", encoding="utf-8")
            (entries / "hello_arg_fn.analysis.txt").write_text("{\"kind\":\"analysis_v1\",\"function_arities\":{\"poison\":0},\"effects\":{\"program\":[],\"functions\":{\"poison\":[]}}}\n", encoding="utf-8")

            source_path = tmp_path / "generic_fn.ksrc"
            source_path.write_text(
                'fn shout(text) {\n'
                '  print concat(text, "!")\n'
                '}\n\n'
                'call shout("hello")\n',
                encoding="utf-8",
            )

            capir = subprocess.run(
                [str(launcher_bin), "selfhost-capir", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(capir.returncode, 0, capir.stderr)
            capir_payload = __import__("json").loads(capir.stdout)
            kir = capir_payload["kir"]
            if isinstance(kir, str):
                kir = __import__("json").loads(kir)
            self.assertEqual(kir["functions"][0]["name"], "shout")
            self.assertEqual(kir["instructions"][0]["name"], "shout")
            self.assertNotIn("poison", __import__("json").dumps(kir, ensure_ascii=False))

            check = subprocess.run(
                [str(launcher_bin), "selfhost-check", "--json", str(self.root / "examples" / "selfhost_frontend.ks"), str(source_path)],
                cwd=dist, check=False, capture_output=True, text=True, env={**os.environ, "PYTHONHOME": "", "PYTHONPATH": ""},
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            check_payload = __import__("json").loads(check.stdout)
            hir = check_payload["hir"]
            if isinstance(hir, str):
                hir = __import__("json").loads(hir)
            self.assertEqual(hir["functions"][0]["name"], "shout")
            self.assertEqual(check_payload["effects"]["functions"], {"shout": ["print"]})
            self.assertEqual(check_payload["value"], "ok")


if __name__ == "__main__":
    unittest.main()
