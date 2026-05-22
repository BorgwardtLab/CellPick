"""Phase 2 GUI smoke tests."""


def test_main_window_constructs_and_closes(qapp) -> None:
    from cellpick.app.ui_main import MainWindow

    window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.windowTitle() == "CellPick"

    window.close()
    qapp.processEvents()


def test_main_window_has_expected_pages(qapp) -> None:
    from cellpick.app.ui_main import MainWindow

    window = MainWindow()

    assert window.stack.count() >= 2
    assert window.img_stack.count() >= 2

    window.close()
