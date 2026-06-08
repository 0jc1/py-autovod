import pytest
import os
import sys
from unittest.mock import patch
from configparser import ConfigParser
import importlib

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestSettings:
    """Test cases for settings module"""

    def test_settings_import(self):
        """Test that settings module imports without errors"""
        try:
            import settings
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import settings: {e}")

    @patch.dict(os.environ, {"OPEN_ROUTER_KEY": "test_key"})
    def test_api_key_from_env(self):
        """Test that API key is loaded from environment"""
        import settings
        importlib.reload(settings)  # ensure env var is read fresh
        assert settings.API_KEY == "test_key"

    @patch.dict(os.environ, {}, clear=True)
    def test_api_key_missing(self):
        """Test behavior when API key is missing"""
        import settings
        importlib.reload(settings)
        assert settings.API_KEY is None

    def test_load_config_reads_file(self, project_root):
        """Test that load_config actually loads config.ini"""
        import settings

        config = settings.load_config("config")
        assert isinstance(config, ConfigParser)
        assert config.has_section("encoding")
        assert config.has_section("upload")

    def test_clipception_enabled_flag(self, project_root):
        """Test that CLIPCEPTION_ENABLED is computed correctly"""
        import settings
        assert isinstance(settings.CLIPCEPTION_ENABLED, bool)
