from src.config import settings, app_config


def test_settings_loads():
    assert settings.telegram_apikey
    assert settings.mariadb_host
    assert settings.database_url.startswith("mysql+aiomysql://")


def test_app_config_has_baskets():
    assert "baskets" in app_config
    assert len(app_config["baskets"]) >= 1


def test_app_config_has_strategies():
    assert "strategies" in app_config
    assert "stop_loss" in app_config["strategies"]
