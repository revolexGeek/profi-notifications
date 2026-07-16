"""Дымовой тест: пакет собран и импортируется, тестовый харнесс работает."""


def test_app_package_imports() -> None:
    import app

    assert app.__version__ == "0.1.0"
