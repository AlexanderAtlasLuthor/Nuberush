import pytest
from pydantic import ValidationError

from app.core.config import AppSettings, AuthSettings


def _build_auth(**overrides) -> AuthSettings:
    payload = {
        "_env_file": None,
        "app_env": "development",
        "jwt_secret_key": "x" * 40,
    }
    payload.update(overrides)
    return AuthSettings(**payload)


class TestJwtSecretEmpty:
    def test_empty_secret_fails_in_development(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            _build_auth(app_env="development", jwt_secret_key="")

    def test_empty_secret_fails_in_production(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            _build_auth(app_env="production", jwt_secret_key="")

    def test_whitespace_only_secret_fails(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            _build_auth(app_env="production", jwt_secret_key="   ")


class TestJwtSecretBlocklist:
    @pytest.mark.parametrize(
        "weak_secret",
        ["change-me", "dev-secret", "secret", "password", "jwt-secret"],
    )
    def test_blocklisted_value_fails_in_production(self, weak_secret: str):
        with pytest.raises(ValidationError, match="known insecure value"):
            _build_auth(app_env="production", jwt_secret_key=weak_secret)

    def test_blocklist_is_case_insensitive(self):
        with pytest.raises(ValidationError, match="known insecure value"):
            _build_auth(app_env="production", jwt_secret_key="CHANGE-ME")

    def test_blocklisted_value_fails_in_staging(self):
        with pytest.raises(ValidationError, match="known insecure value"):
            _build_auth(app_env="staging", jwt_secret_key="change-me")


class TestJwtSecretDevOnlyMarker:
    def test_dev_only_prefix_fails_in_production(self):
        with pytest.raises(ValidationError, match="development-only marker"):
            _build_auth(
                app_env="production",
                jwt_secret_key="dev-only-change-before-production",
            )

    def test_dev_only_prefix_fails_in_staging(self):
        with pytest.raises(ValidationError, match="development-only marker"):
            _build_auth(
                app_env="staging",
                jwt_secret_key="dev-only-anything-here-very-long-string",
            )


class TestJwtSecretLength:
    def test_secret_shorter_than_32_fails_in_production(self):
        with pytest.raises(ValidationError, match="at least 32 characters"):
            _build_auth(app_env="production", jwt_secret_key="a" * 31)

    def test_secret_with_exactly_32_chars_passes_in_production(self):
        settings = _build_auth(app_env="production", jwt_secret_key="a" * 32)
        assert settings.app_env == "production"
        assert len(settings.jwt_secret_key) == 32

    def test_strong_64_char_secret_passes_in_staging(self):
        settings = _build_auth(app_env="staging", jwt_secret_key="b" * 64)
        assert settings.app_env == "staging"
        assert len(settings.jwt_secret_key) == 64


class TestJwtSecretDevelopmentLeniency:
    def test_change_me_is_allowed_in_development(self):
        settings = _build_auth(app_env="development", jwt_secret_key="change-me")
        assert settings.jwt_secret_key == "change-me"

    def test_short_secret_is_allowed_in_development(self):
        settings = _build_auth(app_env="development", jwt_secret_key="abc")
        assert settings.jwt_secret_key == "abc"

    def test_dev_only_marker_is_allowed_in_development(self):
        settings = _build_auth(
            app_env="development",
            jwt_secret_key="dev-only-change-before-production",
        )
        assert settings.jwt_secret_key == "dev-only-change-before-production"


class TestJwtPolicyHonorsEnvVars:
    def test_production_env_var_rejects_weak_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "change-me")
        with pytest.raises(ValidationError, match="known insecure value"):
            AuthSettings(_env_file=None)

    def test_production_env_var_accepts_strong_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "z" * 48)
        settings = AuthSettings(_env_file=None)
        assert settings.app_env == "production"
        assert len(settings.jwt_secret_key) == 48


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
