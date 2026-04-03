"""Tests for powerbi_import.security_validator — path, ZIP, XML, credential security."""

import os
import tempfile
import unittest
import zipfile

from powerbi_import.security_validator import (
    validate_path,
    validate_output_dir,
    safe_zip_extract_member,
    validate_zip_archive,
    safe_parse_xml,
    redact_credentials,
    redact_m_credentials,
    SecurityError,
)


class TestValidatePath(unittest.TestCase):
    """Test path validation and traversal protection."""

    def test_null_byte_rejected(self):
        valid, err = validate_path("/some/path\x00evil", must_exist=False)
        self.assertFalse(valid)
        self.assertIn("null bytes", err)

    def test_empty_path_rejected(self):
        valid, err = validate_path("", must_exist=False)
        self.assertFalse(valid)
        self.assertIn("empty", err.lower())

    def test_existing_file_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"test")
            path = f.name
        try:
            valid, err = validate_path(path, must_exist=True)
            self.assertTrue(valid)
            self.assertIsNone(err)
        finally:
            os.unlink(path)

    def test_nonexistent_file_fails_when_must_exist(self):
        valid, err = validate_path("/no/such/file.json", must_exist=True)
        self.assertFalse(valid)
        self.assertIn("does not exist", err)

    def test_nonexistent_file_ok_when_no_exist_check(self):
        valid, err = validate_path("/no/such/file.json", must_exist=False)
        self.assertTrue(valid)

    def test_extension_whitelist(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"test")
            path = f.name
        try:
            valid, err = validate_path(path, must_exist=True, allowed_extensions={".json"})
            self.assertFalse(valid)
            self.assertIn("not in allowed", err)
        finally:
            os.unlink(path)

    def test_allowed_extension_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"test")
            path = f.name
        try:
            valid, err = validate_path(path, must_exist=True, allowed_extensions={".json"})
            self.assertTrue(valid)
        finally:
            os.unlink(path)


class TestValidateOutputDir(unittest.TestCase):
    def test_empty_path_rejected(self):
        valid, err = validate_output_dir("")
        self.assertFalse(valid)

    def test_null_byte_rejected(self):
        valid, err = validate_output_dir("dir\x00evil")
        self.assertFalse(valid)

    def test_system_dir_rejected(self):
        valid, err = validate_output_dir("C:\\Windows\\System32")
        self.assertFalse(valid)
        self.assertIn("system directory", err.lower())

    def test_normal_dir_passes(self):
        with tempfile.TemporaryDirectory() as td:
            valid, err = validate_output_dir(td)
            self.assertTrue(valid)


class TestZipSlipDefense(unittest.TestCase):
    """Test ZIP slip protection."""

    def test_path_traversal_in_zip_entry(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, "test.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../escape.txt", "malicious")
            with zipfile.ZipFile(zip_path, "r") as zf:
                with self.assertRaises(SecurityError):
                    safe_zip_extract_member(zf, "../escape.txt", target_dir=td)

    def test_safe_entry_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, "test.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("safe/file.txt", "hello")
            with zipfile.ZipFile(zip_path, "r") as zf:
                content = safe_zip_extract_member(zf, "safe/file.txt")
            self.assertEqual(content, b"hello")

    def test_validate_zip_archive_clean(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, "clean.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("data.json", '{"key": "value"}')
            is_safe, issues = validate_zip_archive(zip_path)
            self.assertTrue(is_safe)
            self.assertEqual(issues, [])

    def test_validate_zip_traversal_detected(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, "evil.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../../etc/passwd", "hacked")
            is_safe, issues = validate_zip_archive(zip_path)
            self.assertFalse(is_safe)
            self.assertTrue(any("traversal" in i.lower() for i in issues))

    def test_validate_nonexistent_zip(self):
        is_safe, issues = validate_zip_archive("/no/such/file.zip")
        self.assertFalse(is_safe)


class TestSafeParseXml(unittest.TestCase):
    """Test XXE protection in XML parsing."""

    def test_valid_xml_parsed(self):
        xml = "<root><item>value</item></root>"
        elem = safe_parse_xml(xml)
        self.assertEqual(elem.tag, "root")

    def test_xxe_entity_rejected(self):
        xxe = '<!DOCTYPE foo [<!ENTITY xxe "evil">]><root>&xxe;</root>'
        with self.assertRaises(SecurityError):
            safe_parse_xml(xxe)

    def test_bytes_input(self):
        xml_bytes = b"<root><child/></root>"
        elem = safe_parse_xml(xml_bytes)
        self.assertEqual(elem.tag, "root")


class TestRedactCredentials(unittest.TestCase):
    """Test credential redaction."""

    def test_password_redacted(self):
        text = "password=secret123"
        result = redact_credentials(text)
        self.assertNotIn("secret123", result)
        self.assertIn("REDACTED", result)

    def test_bearer_token_redacted(self):
        text = "Bearer eyJhbGciOiJIUzI1NiJ9"
        result = redact_credentials(text)
        self.assertIn("REDACTED", result)

    def test_api_key_redacted(self):
        text = "api_key=abcdef12345"
        result = redact_credentials(text)
        self.assertIn("REDACTED", result)

    def test_normal_text_unchanged(self):
        text = "SELECT * FROM table WHERE id = 1"
        result = redact_credentials(text)
        self.assertEqual(result, text)

    def test_empty_input(self):
        self.assertEqual(redact_credentials(""), "")
        self.assertIsNone(redact_credentials(None))


class TestRedactMCredentials(unittest.TestCase):
    """Test M query credential redaction."""

    def test_password_in_m_redacted(self):
        m = 'Source = Sql.Database("server", [Password="secret"])'
        result = redact_m_credentials(m)
        self.assertNotIn("secret", result)
        self.assertIn("REDACTED", result)

    def test_empty_m_query(self):
        self.assertEqual(redact_m_credentials(""), "")
        self.assertIsNone(redact_m_credentials(None))


if __name__ == "__main__":
    unittest.main()
