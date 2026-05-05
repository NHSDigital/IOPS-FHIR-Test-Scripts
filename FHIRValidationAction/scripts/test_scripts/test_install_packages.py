"""Tests for install_packages.py - FHIR package dependency installer"""
import base64
import json
import os
import sys
import pytest
from unittest.mock import MagicMock, mock_open, patch, call

# ---------------------------------------------------------------------------
# Make the script importable from the sibling "script" folder.
# Adjust the path if your project layout differs.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))
import install_packages  # noqa: E402  (import after sys.path manipulation)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def tmp_root(tmp_path):
    """A temporary directory that mimics the expected ROOT layout."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    return str(tmp_path)


@pytest.fixture
def sample_package_json():
    return {
        "name": "test-ig",
        "version": "1.0.0",
        "dependencies": {
            "hl7.fhir.r4.core": "4.0.1",
            "hl7.fhir.us.core": "5.0.1",
            "hl7.terminology.r4": "5.3.0",
        },
    }


@pytest.fixture
def mock_tgz(tmp_root):
    """Write a tiny fake .tgz file and return its path."""
    pkg_path = os.path.join(tmp_root, "packages", "hl7.fhir.us.core-5.0.1.tgz")
    with open(pkg_path, "wb") as f:
        f.write(b"fake-tgz-content")
    return pkg_path


# ===========================================================================
# check_package_locally
# ===========================================================================

class TestCheckPackageLocally:
    def test_returns_true_when_tgz_exists(self, tmp_root):
        pkg_id = "hl7.fhir.us.core"
        version = "5.0.1"
        tgz_name = f"{pkg_id}#{version}.tgz"
        open(os.path.join(tmp_root, "packages", tgz_name), "wb").close()

        assert install_packages.check_package_locally(pkg_id, version, tmp_root) is True

    def test_returns_false_when_tgz_missing(self, tmp_root):
        assert (
            install_packages.check_package_locally("missing.pkg", "1.0.0", tmp_root)
            is False
        )

    def test_returns_false_for_empty_packages_dir(self, tmp_root):
        assert (
            install_packages.check_package_locally("any.pkg", "0.0.1", tmp_root)
            is False
        )

    def test_detects_file_in_nested_subdirectory(self, tmp_root):
        pkg_id = "org.example.ig"
        version = "2.1.0"
        nested = os.path.join(tmp_root, "packages", "sub", "nested")
        os.makedirs(nested)
        open(os.path.join(nested, f"{pkg_id}#{version}.tgz"), "wb").close()

        assert install_packages.check_package_locally(pkg_id, version, tmp_root) is True


# ===========================================================================
# download_package
# ===========================================================================

class TestDownloadPackage:
    def test_downloads_and_writes_tgz_on_success(self, tmp_root):
        fake_content = b"tgz-binary-data"
        mock_response = MagicMock(status_code=200, content=fake_content)

        with patch("install_packages.requests.get", return_value=mock_response):
            result = install_packages.download_package(
                "hl7.fhir.us.core", "5.0.1", tmp_root
            )

        assert result is True
        output_path = os.path.join(
            tmp_root, "packages", "hl7.fhir.us.core-5.0.1.tgz"
        )
        assert os.path.exists(output_path)
        with open(output_path, "rb") as f:
            assert f.read() == fake_content

    def test_returns_false_on_404(self, tmp_root, capsys):
        mock_response = MagicMock(status_code=404)

        with patch("install_packages.requests.get", return_value=mock_response):
            result = install_packages.download_package(
                "nonexistent.pkg", "1.0.0", tmp_root
            )

        assert result is False
        captured = capsys.readouterr()
        assert "not found on registry" in captured.out

    def test_calls_correct_simplifier_url(self, tmp_root):
        mock_response = MagicMock(status_code=200, content=b"x")

        with patch("install_packages.requests.get", return_value=mock_response) as mock_get:
            install_packages.download_package("my.pkg", "1.2.3", tmp_root)

        mock_get.assert_called_once_with(
            "https://packages.simplifier.net/my.pkg/1.2.3"
        )


# ===========================================================================
# install_package
# ===========================================================================

class TestInstallPackage:
    def _make_response(self, status_code=200):
        r = MagicMock()
        r.status_code = status_code
        return r

    def test_posts_to_correct_endpoint(self, mock_tgz, tmp_root):
        server_url = "http://localhost:8080/fhir"
        mock_resp = self._make_response(200)

        with patch("install_packages.requests.post", return_value=mock_resp) as mock_post:
            install_packages.install_package(
                "hl7.fhir.us.core", "5.0.1", tmp_root, server_url
            )

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == f"{server_url}/ImplementationGuide/$install"

    def test_payload_contains_base64_encoded_tgz(self, mock_tgz, tmp_root):
        with patch("install_packages.requests.post", return_value=self._make_response()) as mock_post:
            install_packages.install_package(
                "hl7.fhir.us.core", "5.0.1", tmp_root, "http://localhost:8080/fhir"
            )

        payload = mock_post.call_args.kwargs["json"]
        assert payload["resourceType"] == "Parameters"

        params = {p["name"]: p for p in payload["parameter"]}
        assert "npmContent" in params

        # Verify the value actually decodes back to our fake file content
        decoded = base64.b64decode(params["npmContent"]["valueBase64Binary"])
        assert decoded == b"fake-tgz-content"

    def test_uses_fhir_json_content_type(self, mock_tgz, tmp_root):
        with patch("install_packages.requests.post", return_value=self._make_response()) as mock_post:
            install_packages.install_package(
                "hl7.fhir.us.core", "5.0.1", tmp_root, "http://localhost:8080/fhir"
            )

        headers = mock_post.call_args.kwargs["headers"]
        assert headers.get("Content-Type") == "application/fhir+json"

    def test_returns_response_object(self, mock_tgz, tmp_root):
        mock_resp = self._make_response(201)

        with patch("install_packages.requests.post", return_value=mock_resp):
            result = install_packages.install_package(
                "hl7.fhir.us.core", "5.0.1", tmp_root, "http://localhost:8080/fhir"
            )

        assert result is mock_resp


# ===========================================================================
# main()
# ===========================================================================

class TestMain:
    # ---- helpers -----------------------------------------------------------

    def _patch_env(self, tmp_root, package_json_content, monkeypatch):
        """Write a package.json and point ROOT + PACKAGE_PATH at it."""
        test_dir = os.path.join(tmp_root, "Validation-github-action", "test")
        os.makedirs(test_dir)
        pkg_path = os.path.join(test_dir, "package.json")
        with open(pkg_path, "w") as f:
            json.dump(package_json_content, f)

        monkeypatch.setattr(os, "getcwd", lambda: str(tmp_root))

        packages_dir = os.path.join(
            tmp_root, "Validation-github-action", "packages"
        )
        os.makedirs(packages_dir, exist_ok=True)
        return packages_dir

    # ---- tests -------------------------------------------------------------

    def test_returns_0_when_no_package_json(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))
        result = install_packages.main()
        assert result == 0
        assert "skipping" in capsys.readouterr().out.lower()

    def test_returns_0_when_no_dependencies(self, tmp_path, monkeypatch, capsys):
        self._patch_env(tmp_path, {"dependencies": {}}, monkeypatch)
        result = install_packages.main()
        assert result == 0
        assert "no dependencies" in capsys.readouterr().out.lower()

    def test_skips_hl7_fhir_r4_core(self, tmp_path, monkeypatch):
        packages_dir = self._patch_env(
            tmp_path,
            {"dependencies": {"hl7.fhir.r4.core": "4.0.1"}},
            monkeypatch,
        )
        with (
            patch("install_packages.check_package_locally", return_value=True),
            patch("install_packages.install_package") as mock_install,
            patch("install_packages.time.sleep"),
        ):
            result = install_packages.main()

        mock_install.assert_not_called()
        assert result == 0

    def test_installs_non_core_packages(self, tmp_path, monkeypatch):
        packages_dir = self._patch_env(
            tmp_path,
            {
                "dependencies": {
                    "hl7.fhir.r4.core": "4.0.1",
                    "hl7.fhir.us.core": "5.0.1",
                }
            },
            monkeypatch,
        )
        mock_resp = MagicMock()  # truthy → not a failure

        with (
            patch("install_packages.check_package_locally", return_value=True),
            patch("install_packages.install_package", return_value=mock_resp) as mock_install,
            patch("install_packages.time.sleep"),
        ):
            result = install_packages.main()

        mock_install.assert_called_once()
        call_args = mock_install.call_args
        assert call_args.args[0] == "hl7.fhir.us.core"
        assert result == 0

    def test_downloads_package_when_not_cached(self, tmp_path, monkeypatch):
        self._patch_env(
            tmp_path,
            {"dependencies": {"hl7.fhir.us.core": "5.0.1"}},
            monkeypatch,
        )
        mock_resp = MagicMock()

        with (
            patch("install_packages.check_package_locally", return_value=False),
            patch("install_packages.download_package") as mock_dl,
            patch("install_packages.install_package", return_value=mock_resp),
            patch("install_packages.time.sleep"),
        ):
            install_packages.main()

        mock_dl.assert_called_once_with("hl7.fhir.us.core", "5.0.1", pytest.approx)

    def test_skips_download_when_package_cached(self, tmp_path, monkeypatch):
        self._patch_env(
            tmp_path,
            {"dependencies": {"hl7.fhir.us.core": "5.0.1"}},
            monkeypatch,
        )
        mock_resp = MagicMock()

        with (
            patch("install_packages.check_package_locally", return_value=True),
            patch("install_packages.download_package") as mock_dl,
            patch("install_packages.install_package", return_value=mock_resp),
            patch("install_packages.time.sleep"),
        ):
            install_packages.main()

        mock_dl.assert_not_called()

    def test_returns_1_and_lists_failed_packages(self, tmp_path, monkeypatch, capsys):
        self._patch_env(
            tmp_path,
            {"dependencies": {"hl7.fhir.us.core": "5.0.1"}},
            monkeypatch,
        )
        with (
            patch("install_packages.check_package_locally", return_value=True),
            patch("install_packages.install_package", return_value=False),  # falsy = failure
            patch("install_packages.time.sleep"),
        ):
            result = install_packages.main()

        assert result == 1
        output = capsys.readouterr().out
        assert "failed" in output.lower()
        assert "hl7.fhir.us.core" in output

    def test_sleeps_between_package_installations(self, tmp_path, monkeypatch):
        self._patch_env(
            tmp_path,
            {
                "dependencies": {
                    "hl7.fhir.us.core": "5.0.1",
                    "hl7.terminology.r4": "5.3.0",
                }
            },
            monkeypatch,
        )
        mock_resp = MagicMock()

        with (
            patch("install_packages.check_package_locally", return_value=True),
            patch("install_packages.install_package", return_value=mock_resp),
            patch("install_packages.time.sleep") as mock_sleep,
        ):
            install_packages.main()

        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2)

    def test_reports_correct_installed_count(self, tmp_path, monkeypatch, capsys):
        """num_packages should exclude hl7.fhir.r4.core from the success count."""
        self._patch_env(
            tmp_path,
            {
                "dependencies": {
                    "hl7.fhir.r4.core": "4.0.1",
                    "hl7.fhir.us.core": "5.0.1",
                    "hl7.terminology.r4": "5.3.0",
                }
            },
            monkeypatch,
        )
        mock_resp = MagicMock()

        with (
            patch("install_packages.check_package_locally", return_value=True),
            patch("install_packages.install_package", return_value=mock_resp),
            patch("install_packages.time.sleep"),
        ):
            result = install_packages.main()

        assert result == 0
        assert "2" in capsys.readouterr().out  # 3 total − 1 core = 2
