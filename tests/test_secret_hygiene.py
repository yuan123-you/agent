"""Credential hygiene regressions; never include secret values in failures."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SecretHygieneTests(unittest.TestCase):
    def tracked_paths(self):
        raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"])
        return [p for p in raw.decode("utf-8").split("\0") if p]

    def test_no_provider_keys_or_private_keys_in_tracked_text(self):
        pattern = re.compile(rb"(?:\b[a-fA-F0-9]{32}\.[A-Za-z0-9]{16,64}\b|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
        found = []
        for rel in self.tracked_paths():
            p = ROOT / rel
            if p.is_file() and p.suffix.lower() not in {".docx", ".pptx", ".pdf", ".png", ".jpg", ".webp"}:
                if pattern.search(p.read_bytes()):
                    found.append(rel)
        self.assertEqual(found, [], "Credential-shaped values found in: " + ", ".join(found))

    def test_no_sensitive_database_exports_are_tracked(self):
        found = [p for p in self.tracked_paths() if re.search(r"(?:^|/)(?:.*seed.*export|.*data.*dump).*\.sql$", p, re.I)]
        self.assertEqual(found, [], "User-data exports must stay local")

    def test_local_secret_paths_are_ignored(self):
        for rel in [".env.staging", "ai-service/.env.local", ".ssh_key_deploy", "deploy/server.pem", ".deployment-private/token.json", ".codex-deploy/server.key"]:
            with self.subTest(path=rel):
                result = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", rel])
                self.assertEqual(result.returncode, 0, "Secret path is not ignored")

    def test_env_templates_do_not_store_credential_values(self):
        for rel in [".env.example", ".env.production.example", "ai-service/.env.example"]:
            p = ROOT / rel
            if not p.exists(): continue
            for line in p.read_text(encoding="utf-8").splitlines():
                match = re.match(r"([A-Z_]*(?:PASSWORD|SECRET|TOKEN|API_KEY)[A-Z_]*)=(.*)$", line)
                if match:
                    self.assertFalse(bool(match.group(2).strip()), p.name + ":" + match.group(1))

    def test_seed_accounts_do_not_contain_login_passwords(self):
        for rel in ["backend/src/main/resources/data.sql", "server/src/main/resources/db/03-seed-data.sql"]:
            p = ROOT / rel
            if not p.exists(): continue
            text = p.read_text(encoding="utf-8")
            self.assertFalse(bool(re.search(r"\$2[aby]\$\d\d\$", text)), "Static seed password hashes must not be shipped")
            for line in text.splitlines():
                if line.startswith("INSERT INTO user_account "):
                    match = re.search(r"VALUES \('[^']*', '[^']*', '[^']*', '([^']*)'", line)
                    self.assertIsNotNone(match)
                    self.assertFalse(bool(match.group(1)), "Seed login secret must be disabled")
                    self.assertFalse("password=VALUES(password)" in line, "Restart must not overwrite passwords")

    def test_docker_contexts_exclude_private_material(self):
        text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for pattern in [".env", "**/.env.*", "**/.ssh_key*", "**/.deployment-private", "**/*-data-export.sql"]:
            self.assertTrue(pattern in text, "Docker exclusion missing: " + pattern)

    def test_exam_password_reset_input_is_masked(self):
        for rel in ["src/views/admin/StudentManage.vue", "src/views/admin/TeacherManage.vue"]:
            p = ROOT / rel
            if not p.exists(): continue
            text = p.read_text(encoding="utf-8")
            self.assertFalse("window.prompt" in text, "Password must not be entered into an unmasked prompt")
            self.assertTrue('type="password"' in text, "Masked password input is required")

    def test_runtime_configs_have_no_fixed_secret_defaults(self):
        files = [ROOT / "docker-compose.yml"]
        for folder in ["backend/src/main/resources", "server/src/main/resources"]:
            files.extend(p for p in (ROOT / folder).glob("application*.yml") if "test" not in p.name)
        pattern = re.compile(r"\$\{([A-Z_]*(?:PASSWORD|SECRET|TOKEN|API_KEY)[A-Z_]*):([^}]*)\}")
        found = []
        for p in files:
            if not p.exists():
                continue
            for match in pattern.finditer(p.read_text(encoding="utf-8")):
                # Required Compose interpolation is a message, not a default value.
                if match.group(2).lstrip("-") and not match.group(2).startswith("?"):
                    found.append(p.name + ":" + match.group(1))
        self.assertEqual(found, [], "Fixed runtime credentials found in: " + ", ".join(found))

if __name__ == "__main__":
    unittest.main()
