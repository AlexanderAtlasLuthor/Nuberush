import pytest

from app.core.config import AppSettings


# F2.22.2.F — the legacy self-hosted JWT is gone, and with it the
# `AuthSettings` model and its secret-strength policy. The JWT secret
# tests that used to live here were removed. The CORS-origins parsing
# tests below still cover the surviving `AppSettings` behaviour.


class TestCorsOriginsParsing:
    def test_defaults_when_no_env_var_is_set(self):
        settings = AppSettings(_env_file=None)
        assert settings.backend_cors_origins == [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    def test_csv_string_is_split_into_list(self):
        settings = AppSettings(
            _env_file=None,
            backend_cors_origins="http://a.com,http://b.com,http://c.com",
        )
        assert settings.backend_cors_origins == [
            "http://a.com",
            "http://b.com",
            "http://c.com",
        ]

    def test_whitespace_around_entries_is_trimmed(self):
        settings = AppSettings(
            _env_file=None,
            backend_cors_origins="http://a.com, http://b.com ,  http://c.com",
        )
        assert settings.backend_cors_origins == [
            "http://a.com",
            "http://b.com",
            "http://c.com",
        ]

    def test_empty_entries_are_ignored(self):
        settings = AppSettings(
            _env_file=None,
            backend_cors_origins="http://a.com,,http://b.com,, ,",
        )
        assert settings.backend_cors_origins == [
            "http://a.com",
            "http://b.com",
        ]

    def test_value_loaded_from_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "BACKEND_CORS_ORIGINS",
            "http://x.com, http://y.com",
        )
        settings = AppSettings(_env_file=None)
        assert settings.backend_cors_origins == ["http://x.com", "http://y.com"]

    def test_list_value_is_passed_through_unchanged(self):
        settings = AppSettings(
            _env_file=None,
            backend_cors_origins=["http://a.com", "http://b.com"],
        )
        assert settings.backend_cors_origins == ["http://a.com", "http://b.com"]
