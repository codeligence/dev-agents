import pytest

from core.exceptions import GitOperationError
from core.git.clone_url import host_from_url, validate_clone_url


class TestHostFromUrl:
    """Tests for extracting the host (with port) from a URL."""

    def test_plain_host(self):
        assert host_from_url("https://gitlab.example.com/api/v4") == (
            "gitlab.example.com"
        )

    def test_preserves_port(self):
        assert host_from_url("https://gitlab.example.com:8443/api/v4") == (
            "gitlab.example.com:8443"
        )

    def test_strips_userinfo(self):
        assert host_from_url("https://user:pw@gitlab.example.com/") == (
            "gitlab.example.com"
        )

    def test_no_host(self):
        assert host_from_url("not a url") == ""


class TestValidateCloneUrl:
    """Tests for validating clone URLs against the expected host and scheme."""

    def test_https_matching_host_passes(self):
        validate_clone_url(
            "https://gitlab.example.com/group/repo.git",
            expected_host="gitlab.example.com",
        )

    def test_http_rejected(self):
        with pytest.raises(GitOperationError, match="must use https"):
            validate_clone_url(
                "http://gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com",
            )

    def test_other_scheme_rejected(self):
        with pytest.raises(GitOperationError, match="must use https"):
            validate_clone_url(
                "ssh://gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com",
            )

    def test_mismatched_host_rejected(self):
        with pytest.raises(GitOperationError, match="does not match"):
            validate_clone_url(
                "https://evil.example.com/group/repo.git",
                expected_host="gitlab.example.com",
            )

    def test_host_comparison_is_case_insensitive(self):
        validate_clone_url(
            "https://GitLab.Example.com/group/repo.git",
            expected_host="gitlab.example.com",
        )
        validate_clone_url(
            "https://gitlab.example.com/group/repo.git",
            expected_host="GITLAB.EXAMPLE.COM",
        )

    def test_scheme_comparison_is_case_insensitive(self):
        validate_clone_url(
            "HTTPS://gitlab.example.com/group/repo.git",
            expected_host="gitlab.example.com",
        )

    def test_port_must_match(self):
        validate_clone_url(
            "https://gitlab.example.com:8443/group/repo.git",
            expected_host="gitlab.example.com:8443",
        )
        with pytest.raises(GitOperationError, match="does not match"):
            validate_clone_url(
                "https://gitlab.example.com:8443/group/repo.git",
                expected_host="gitlab.example.com",
            )
        with pytest.raises(GitOperationError, match="does not match"):
            validate_clone_url(
                "https://gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com:8443",
            )

    def test_userinfo_rejected(self):
        with pytest.raises(GitOperationError, match="embed credentials"):
            validate_clone_url(
                "https://oauth2:token@gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com",
            )

    def test_userinfo_error_does_not_leak_secret(self):
        with pytest.raises(GitOperationError) as exc_info:
            validate_clone_url(
                "https://oauth2:s3cr3t@gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com",
            )
        assert "s3cr3t" not in str(exc_info.value)

    def test_allow_insecure_permits_http(self):
        validate_clone_url(
            "http://gitlab.example.com/group/repo.git",
            expected_host="gitlab.example.com",
            allow_insecure=True,
        )

    def test_allow_insecure_still_enforces_host(self):
        with pytest.raises(GitOperationError, match="does not match"):
            validate_clone_url(
                "http://evil.example.com/group/repo.git",
                expected_host="gitlab.example.com",
                allow_insecure=True,
            )

    def test_allow_insecure_still_rejects_other_schemes(self):
        with pytest.raises(GitOperationError, match="must use https or http"):
            validate_clone_url(
                "ssh://gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com",
                allow_insecure=True,
            )

    def test_allow_insecure_still_rejects_userinfo(self):
        with pytest.raises(GitOperationError, match="embed credentials"):
            validate_clone_url(
                "http://user@gitlab.example.com/group/repo.git",
                expected_host="gitlab.example.com",
                allow_insecure=True,
            )

    def test_empty_expected_host_rejected(self):
        with pytest.raises(GitOperationError, match="requires an expected host"):
            validate_clone_url(
                "https://gitlab.example.com/group/repo.git", expected_host=""
            )
