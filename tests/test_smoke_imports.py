"""Phase 1 smoke tests for basic package/module importability."""


def test_package_importable() -> None:
    import cellpick  # noqa: F401


def test_core_modules_importable() -> None:
    import cellpick.app.algorithms  # noqa: F401
    import cellpick.app.core.channel  # noqa: F401
    import cellpick.app.core.polygon  # noqa: F401
    import cellpick.app.io.export  # noqa: F401
    import cellpick.app.io.xml_io  # noqa: F401
