import math
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional

import lxml.etree as etree
import numpy as np
import pandas as pd
from czifile import imread as cziimread
from pathlib import Path
from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QObject,
    QPointF,
    QRectF,
    Qt,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from tifffile import imread as tifimread

from .components import CHANNEL_COLORS, AppState, AppStateManager, Polygon
from .image_viewer import ImageViewer
from .ui_components import (
    AnimatedButton,
    ClickableColorLabel,
    ClickableLabel,
    ProgressDialog,
)
from .utils import ImXML

if sys.platform == "darwin":
    try:
        import tempfile

        from AppKit import NSApplication, NSImage

        current_dir = Path(__file__).parent.parent
        logo_path = current_dir / "assets" / "logo.png"
        with open(logo_path, "rb") as f:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(f.read())
            tmp.close()
            icon_path = tmp.name
        appkit_app = NSApplication.sharedApplication()
        appkit_app.setApplicationIconImage_(
            NSImage.alloc().initWithContentsOfFile_(icon_path)
        )
    except ImportError:
        print("PyObjC is not installed. Dock icon will not be set.")


class ScrollableContainer(QWidget):
    inner_layout: QVBoxLayout

    def __init__(self, height: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.inner_layout = QVBoxLayout(content)
        self.inner_layout.setSpacing(0)  # Reduce spacing between items
        self.inner_layout.setContentsMargins(0, 0, 0, 0)  # Reduce margins
        content.setStyleSheet("background-color: white;")
        scroll.setStyleSheet("background-color: white; border: none")
        scroll.setWidget(content)
        layout.addWidget(scroll)


class SelectionPage(QWidget):
    channel_control_panel: ScrollableContainer
    add_channel_btn: AnimatedButton
    load_shapes_btn: AnimatedButton
    gamma_slider: QSlider
    refresh_btn: AnimatedButton
    reset_btn: AnimatedButton
    next_btn: AnimatedButton
    buttons: List[Any]

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.channel_control_panel = ScrollableContainer(height=120)
        button_panel1 = QGroupBox("Load Image")
        button_layout1 = QVBoxLayout(button_panel1)
        button_panel2 = QGroupBox("Image Adjustments")
        button_layout2 = QVBoxLayout(button_panel2)
        button_panel3 = QGroupBox("Cell Shapes")
        button_layout3 = QVBoxLayout(button_panel3)
        self.add_channel_btn = AnimatedButton("Add channel")
        self.load_shapes_btn = AnimatedButton("Load from file")
        self.select_shape_color_btn = AnimatedButton("Select color")
        self.gamma_slider = QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(-100, 100)
        self.gamma_slider.setValue(0)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.refresh_btn = AnimatedButton("Refresh")
        self.reset_btn = AnimatedButton("Reset view")
        self.next_btn = AnimatedButton(
            "Next", color1="87, 143, 202", color2="54, 116, 181"
        )
        button_layout1.addWidget(self.add_channel_btn)
        button_layout1.addWidget(self.channel_control_panel)
        button_layout2.addWidget(QLabel("Brightness"))
        button_layout2.addWidget(self.gamma_slider)
        button_layout2.addWidget(QLabel("Contrast"))
        button_layout2.addWidget(self.contrast_slider)
        button_layout2.addWidget(self.refresh_btn)
        button_layout3.addWidget(self.load_shapes_btn)
        button_layout3.addWidget(self.select_shape_color_btn)
        layout.addWidget(button_panel1)
        layout.addWidget(button_panel2)
        layout.addWidget(button_panel3)
        layout.addWidget(self.reset_btn)
        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addWidget(self.next_btn)
        self.buttons = self.findChildren(AnimatedButton)
        self.buttons.append(self.gamma_slider)
        self.buttons.append(self.contrast_slider)
        self.select_shape_color_btn.clicked.connect(self.pick_shape_color)

    def pick_shape_color(self):
        # Robustly find the MainWindow and use its shape_outline_color
        main_window = self.parent()
        while main_window and not hasattr(main_window, "shape_outline_color"):
            main_window = main_window.parent()
        if main_window and hasattr(main_window, "shape_outline_color"):
            color = QColorDialog.getColor(
                main_window.shape_outline_color, self, "Select shape outline color"
            )
            if color.isValid():
                main_window.shape_outline_color = color
            # Repaint shapes with the selected color
            if hasattr(main_window, "image_viewer"):
                main_window.image_viewer.update_polygon_display()


class ActionPage(QWidget):
    back_btn: AnimatedButton
    add_lnd_btn: AnimatedButton
    delete_last_point_lnd_btn: AnimatedButton
    confirm_lnd_btn: AnimatedButton
    cancel_lnd_btn: AnimatedButton
    delete_lnd_btn: AnimatedButton
    add_ar_btn: AnimatedButton
    delete_last_point_ar_btn: AnimatedButton
    confirm_ar_btn: AnimatedButton
    delete_ar_btn: AnimatedButton
    select_shapes_btn: AnimatedButton
    k_box: QSpinBox
    add_shapes_btn: AnimatedButton
    rem_shapes_btn: AnimatedButton
    export_btn: AnimatedButton
    load_lnd_btn: AnimatedButton
    load_ar_btn: AnimatedButton
    buttons: List[Any]

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        button_panel1 = QGroupBox("Landmarks")
        button_layout1 = QVBoxLayout(button_panel1)
        button_panel2 = QGroupBox("Active Regions")
        button_layout2 = QVBoxLayout(button_panel2)
        button_panel3 = QGroupBox("Shape Selection")
        button_layout3 = QVBoxLayout(button_panel3)
        self.back_btn = AnimatedButton(
            "Home", color1="87, 143, 202", color2="54, 116, 181"
        )
        self.add_lnd_btn = AnimatedButton("Add Landmark")
        self.delete_last_point_lnd_btn = AnimatedButton("Undo", size=(32, 96))
        self.confirm_lnd_btn = AnimatedButton("Confirm", size=(32, 96))
        self.cancel_lnd_btn = AnimatedButton("Cancel")
        self.delete_lnd_btn = AnimatedButton("Delete Landmark")
        self.add_ar_btn = AnimatedButton("Add AR")
        self.delete_last_point_ar_btn = AnimatedButton("Undo", size=(32, 96))
        self.confirm_ar_btn = AnimatedButton("Confirm", size=(32, 96))
        self.delete_ar_btn = AnimatedButton("Delete AR")
        self.select_shapes_btn = AnimatedButton("Automatic Selection")
        self.k_box = QSpinBox()
        self.k_box.setMinimum(0)
        self.k_box.setMaximum(10000)
        self.clustering_type = QComboBox()
        self.clustering_type.addItems(
            ["Select k over union of regions", "Select k per region"]
        )
        self.add_shapes_btn = AnimatedButton("Add", size=(32, 96))
        self.rem_shapes_btn = AnimatedButton("Delete", size=(32, 96))
        self.export_btn = AnimatedButton(
            "Export Selected Cells",
            color1="34, 197, 94",
            color2="21, 128, 61",
        )
        self.load_lnd_btn = AnimatedButton("Load from file")
        self.load_ar_btn = AnimatedButton("Load from file")

        button_layout1.addWidget(self.load_lnd_btn)
        button_layout2.addWidget(self.load_ar_btn)
        button_layout1.addWidget(self.add_lnd_btn)
        subwidget1 = QWidget()
        sublayout1 = QHBoxLayout(subwidget1)
        sublayout1.setContentsMargins(0, 0, 0, 0)
        sublayout1.setSpacing(8)
        sublayout1.addWidget(self.confirm_lnd_btn)
        sublayout1.addWidget(self.delete_last_point_lnd_btn)
        button_layout1.addWidget(subwidget1)
        button_layout1.addWidget(self.delete_lnd_btn)
        button_layout2.addWidget(self.add_ar_btn)
        subwidget2 = QWidget()
        sublayout2 = QHBoxLayout(subwidget2)
        sublayout2.setContentsMargins(0, 0, 0, 0)
        sublayout2.setSpacing(8)
        sublayout2.addWidget(self.confirm_ar_btn)
        sublayout2.addWidget(self.delete_last_point_ar_btn)
        button_layout2.addWidget(subwidget2)
        button_layout2.addWidget(self.delete_ar_btn)
        button_layout3.addWidget(self.k_box)
        button_layout3.addWidget(self.clustering_type)
        button_layout3.addWidget(self.select_shapes_btn)

        subwidget3 = QWidget()
        sublayout3 = QHBoxLayout(subwidget3)
        sublayout3.setContentsMargins(0, 0, 0, 0)
        sublayout3.setSpacing(8)
        sublayout3.addWidget(self.add_shapes_btn)
        sublayout3.addWidget(self.rem_shapes_btn)
        button_layout3.addWidget(subwidget3)

        layout.addWidget(button_panel2)
        layout.addWidget(button_panel1)
        layout.addWidget(button_panel3)

        layout.addWidget(self.export_btn)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addWidget(self.back_btn)
        self.buttons = self.findChildren(AnimatedButton)
        self.buttons.append(self.k_box)


class MainWindow(QMainWindow):
    channels: List[str]
    state: AppStateManager
    stack: QStackedWidget
    page1: SelectionPage
    page2: ActionPage
    img_stack: QStackedWidget
    image_viewer: ImageViewer
    logo: QWidget
    scale: float
    channel_control: QVBoxLayout
    _shape_loader_thread: QThread = None
    _shape_loader_worker: QObject = None
    shape_outline_color: QColor

    def __init__(self) -> None:
        super().__init__()
        self.image_resolution = 25000
        self.channels: List[str] = []
        self.state = AppStateManager()
        self.state.main_window = self
        self.setWindowTitle("CellPick")
        # Set window icon
        current_dir = Path(__file__).parent.parent
        logo_svg_path = current_dir / "assets" / "logo.svg"
        with open(logo_svg_path, "rb") as f:
            svg_bytes = f.read()
        # QIcon does not support SVG directly from bytes, so use QPixmap if possible
        # If you want to use SVG as icon, you may need to convert it to PNG or use QSvgWidget for display
        # Here, we use QPixmap for icon (may require cairosvg or similar for SVG to PNG conversion if needed)
        # For now, fallback to not setting icon if conversion is not possible
        try:
            svg_renderer = QSvgRenderer(QByteArray(svg_bytes))
            pixmap = QPixmap(256, 256)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()
            self.setWindowIcon(QIcon(pixmap))
        except Exception:
            pass
        self.setGeometry(100, 100, 1000, 800)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        self.stack = QStackedWidget()
        self.page1 = SelectionPage()
        self.page2 = ActionPage()
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        main_layout.addWidget(self.stack)
        self.img_stack = QStackedWidget()
        self.image_viewer = ImageViewer(self.state)
        self.logo = QWidget()
        self.scale = 1.0
        hcenter_layout = QHBoxLayout(self.logo)
        # Import SVG logo
        current_dir = Path(__file__).parent.parent
        logo_svg_path = current_dir / "assets" / "logo.svg"
        with open(logo_svg_path, "rb") as f:
            svg_bytes = f.read()
        svg_widget = QSvgWidget()
        svg_widget.load(svg_bytes)
        svg_widget.setFixedSize(400, 400)
        hcenter_layout.addWidget(svg_widget)
        self.img_stack.addWidget(self.logo)
        self.img_stack.addWidget(self.image_viewer)
        main_layout.addWidget(self.img_stack, stretch=4)
        self.channel_control = self.page1.channel_control_panel.inner_layout
        self.page1.next_btn.clicked.connect(self.goto_second_page)
        self.page2.back_btn.clicked.connect(self.goto_first_page)
        self.page1.load_shapes_btn.clicked.connect(self.load_shapes)
        self.page1.add_channel_btn.clicked.connect(self.add_channel)
        self.page1.gamma_slider.valueChanged.connect(self.update_gamma)
        self.page1.contrast_slider.valueChanged.connect(self.update_contrast)
        self.page1.refresh_btn.clicked.connect(self.image_viewer.update_display)
        self.page1.reset_btn.clicked.connect(self.reset_view)
        self.page2.add_lnd_btn.clicked.connect(self.toggle_landmark_selection)
        self.page2.confirm_lnd_btn.clicked.connect(self.confirm_landmark)
        self.page2.delete_lnd_btn.clicked.connect(self.toggle_landmark_deletion)
        self.page2.delete_last_point_lnd_btn.clicked.connect(self.delete_last_lnd_point)
        self.page2.add_ar_btn.clicked.connect(self.toggle_ar_selection)
        self.page2.confirm_ar_btn.clicked.connect(self.confirm_ar)
        self.page2.delete_ar_btn.clicked.connect(self.toggle_ar_deletion)
        self.page2.delete_last_point_ar_btn.clicked.connect(self.delete_last_ar_point)
        self.page2.select_shapes_btn.clicked.connect(self.select_shapes)
        self.page2.add_shapes_btn.clicked.connect(self.toggle_shape_add)
        self.page2.rem_shapes_btn.clicked.connect(self.toggle_shape_rem)
        self.page2.export_btn.clicked.connect(self.export_selected_shapes)
        self.page2.load_lnd_btn.clicked.connect(self.load_landmarks_from_file)
        self.page2.load_ar_btn.clicked.connect(self.load_ar_from_file)
        self.reset_home_buttons()
        self.state.state = AppState.MAIN
        self.reset_main_buttons()
        self.state.state = AppState.HOME
        self.shape_outline_color = QColor(255, 255, 255)

    def goto_first_page(self) -> None:
        self.state.state = AppState.HOME
        self.stack.setCurrentWidget(self.page1)

    def goto_second_page(self) -> None:
        self.state.state = AppState.MAIN
        self.stack.setCurrentWidget(self.page2)

    def update_gamma(self, value: int) -> None:
        self.image_viewer.gamma = np.exp(value / 20.0)

    def update_contrast(self, value: int) -> None:
        # Map slider value (-100 to 100) to contrast factor (0.5 to 2.0)
        self.image_viewer.contrast = 1.0 + value / 100.0

    def reset_view(self) -> None:
        factor = 1.0 / self.image_viewer.graphics_view.zoom_factor
        self.image_viewer.graphics_view.scale(factor, factor)
        self.image_viewer.graphics_view.zoom_factor = 1.0

    def add_channel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Channel Image",
            "",
            "Image Files (*.tif *.tiff *.czi);;All Files (*)",
        )
        if file_path:
            if file_path[-3:] == "czi":
                image_data = cziimread(file_path).squeeze()
            else:
                image_data = tifimread(file_path).squeeze()

            if len(image_data.shape) not in [2, 3]:
                QMessageBox.warning(self, "Error", "Image must be 2D or 3D")
                return
            if len(image_data.shape) == 2:
                image_data = image_data[..., None]
            
            ch_idx = np.argmin(image_data.shape)
            image_data = np.moveaxis(image_data, ch_idx, -1) # now it's (H, W, C)
            
            # Downsample image to full HD resolution (minimum side 1080px, keep aspect ratio)
            max_side = max(image_data.shape[0], image_data.shape[1])
            if max_side > self.image_resolution:
                c = image_data.shape[2]
                inv_scale = math.ceil(max_side // self.image_resolution)
                self.scale /= inv_scale

                new_shape = (
                    image_data.shape[0] // inv_scale,
                    image_data.shape[1] // inv_scale,
                )
                image_data = image_data[::inv_scale, ::inv_scale, :].copy()
                # image_data = image_data.reshape(new_shape[0], inv_scale, new_shape[1], inv_scale, c).mean(axis=(1, 3))

            for chan_id in range(image_data.shape[-1]):
                # Prompt user for channel name
                default_name = file_path.split("/")[-1]
                channel_name, ok = QInputDialog.getText(
                    self,
                    "Channel Name",
                    "Enter a name for this channel:",
                    text=default_name,
                )
                if not ok:
                    return  # User cancelled the dialog
                if not channel_name.strip():
                    QMessageBox.warning(self, "Error", "Channel name cannot be empty")
                    return

                # Prompt user for channel color
                color_dialog = QColorDialog(self)
                color_dialog.setWindowTitle("Select Channel Color")
                color_dialog.setCurrentColor(QColor(255, 255, 255))  # Default to white
                if color_dialog.exec() == QColorDialog.Accepted:
                    selected_color = color_dialog.currentColor()
                    custom_color = np.array(
                        [
                            selected_color.red(),
                            selected_color.green(),
                            selected_color.blue(),
                        ]
                    )
                else:
                    return  # User cancelled the color dialog

                error_id = self.image_viewer.add_channel(
                    image_data[:, :, chan_id], channel_name, custom_color
                )
                if error_id == 1:
                    QMessageBox.warning(
                        self, "Error", "Image must be 2D or 3D (single channel)"
                    )
                    return
                if error_id == 2:
                    QMessageBox.warning(
                        self, "Error", "Loaded channels have different shapes"
                    )
                    return
                self.channels.append(file_path)
                self.add_channel_control(
                    channel_name, len(self.image_viewer.channels) - 1
                )
                self.state.enable_advanced_home()
                self.img_stack.setCurrentWidget(self.image_viewer)

    def add_channel_control(self, name: str, channel_idx: int) -> None:
        channel_widget = QWidget()
        channel_layout = QHBoxLayout(channel_widget)

        # Create clickable name label
        name_label = ClickableLabel(name)
        name_label.clicked.connect(lambda: self.rename_channel(channel_idx))
        channel_layout.addWidget(name_label)

        # Create checkbox for visibility
        cb = QCheckBox()
        cb.setChecked(True)
        cb.stateChanged.connect(
            lambda state, idx=channel_idx: self.toggle_channel(idx, state)
        )
        channel_layout.addWidget(cb)

        # Create clickable color label
        if (
            channel_idx < len(self.image_viewer.channels)
            and self.image_viewer.channels[channel_idx].custom_color is not None
        ):
            color = self.image_viewer.channels[channel_idx].custom_color
        else:
            color = CHANNEL_COLORS[channel_idx % len(CHANNEL_COLORS)]

        color_label = ClickableColorLabel(color)
        color_label.clicked.connect(lambda: self.change_channel_color(channel_idx))
        channel_layout.addWidget(color_label)

        # Store references for later updates
        channel_widget.name_label = name_label
        channel_widget.color_label = color_label
        channel_widget.channel_idx = channel_idx

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.clicked.connect(lambda _, idx=channel_idx: self.remove_channel(idx))
        channel_layout.addWidget(remove_btn)
        self.channel_control.addWidget(channel_widget)

    def rename_channel(self, channel_idx: int) -> None:
        """Rename a channel by showing a text input dialog."""
        if 0 <= channel_idx < len(self.image_viewer.channels):
            current_name = self.image_viewer.channels[channel_idx].name
            new_name, ok = QInputDialog.getText(
                self,
                "Rename Channel",
                "Enter new name for this channel:",
                text=current_name,
            )
            if ok and new_name.strip():
                self.image_viewer.channels[channel_idx].name = new_name.strip()
                # Update the name label in the UI
                for i in range(self.channel_control.count()):
                    item = self.channel_control.itemAt(i)
                    if item.widget() and hasattr(item.widget(), "channel_idx"):
                        if item.widget().channel_idx == channel_idx:
                            item.widget().name_label.setText(new_name.strip())
                            break

    def change_channel_color(self, channel_idx: int) -> None:
        """Change a channel's color by showing a color picker dialog."""
        if 0 <= channel_idx < len(self.image_viewer.channels):
            # Get current color
            channel = self.image_viewer.channels[channel_idx]
            if channel.custom_color is not None:
                current_color = QColor(
                    channel.custom_color[0],
                    channel.custom_color[1],
                    channel.custom_color[2],
                )
            else:
                default_color = CHANNEL_COLORS[channel_idx % len(CHANNEL_COLORS)]
                current_color = QColor(
                    default_color[0], default_color[1], default_color[2]
                )

            # Show color picker
            color_dialog = QColorDialog(self)
            color_dialog.setWindowTitle("Select Channel Color")
            color_dialog.setCurrentColor(current_color)
            if color_dialog.exec() == QColorDialog.Accepted:
                selected_color = color_dialog.currentColor()
                new_color = np.array(
                    [
                        selected_color.red(),
                        selected_color.green(),
                        selected_color.blue(),
                    ]
                )

                # Update the channel's custom color
                channel.custom_color = new_color

                # Update the color label in the UI
                for i in range(self.channel_control.count()):
                    item = self.channel_control.itemAt(i)
                    if item.widget() and hasattr(item.widget(), "channel_idx"):
                        if item.widget().channel_idx == channel_idx:
                            item.widget().color_label.set_color(new_color)
                            break

                # Update the display
                self.image_viewer.update_display()

    def remove_channel(self, channel_idx: int) -> None:
        if 0 <= channel_idx < len(self.image_viewer.channels):
            self.channels.pop(channel_idx)
            self.image_viewer.channels.pop(channel_idx)
            self.rebuild_channel_controls()
            self.image_viewer.update_display()
        if len(self.channels) == 0:
            self.state.to_home()

    def rebuild_channel_controls(self) -> None:
        while self.channel_control.count():
            item = self.channel_control.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for idx, channel in enumerate(self.image_viewer.channels):
            self.add_channel_control(channel.name, idx)

    def toggle_channel(self, channel_idx: int, visible: bool) -> None:
        if 0 <= channel_idx < len(self.image_viewer.channels):
            self.image_viewer.channels[channel_idx].visible = visible
            self.image_viewer.update_display()

    def load_shapes(self) -> None:
        xml_path, _ = QFileDialog.getOpenFileName(
            self, "Open XML containing shapes", "", "XML Files (*.xml);;All Files (*)"
        )
        if not xml_path:
            return
        meta_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image Metadata File", "", "TXT Files (*.txt);;All Files (*)"
        )
        if not meta_path:
            return
        if not self.image_viewer.channels:
            QMessageBox.warning(self, "Warning", "Please load an image first")
            return
        try:
            meta = pd.read_csv(meta_path, sep="\t")
            calibration = meta.iloc[0, 0]
            self.im_xml = ImXML(meta_path, xml_path, '')
            self.im_xml.im_shape = self.image_viewer.channels[0].image_data.shape
            self.im_xml.calibration(calibration)
            self.state.reset_shapes()
            total = self.im_xml.dvpxml.n_shapes
            progress_dialog = QProgressDialog(
                "Loading shapes...", "Cancel", 0, total, self
            )
            progress_dialog.setWindowModality(Qt.ApplicationModal)
            progress_dialog.setValue(0)
            progress_dialog.show()
            all_shapes = []
            for i in range(1, total + 1):
                try:
                    x, y = self.im_xml.dvpxml.return_shape(i)
                    x_px = self.im_xml.fxx(y)
                    y_px = self.im_xml.fyy(x)
                    if len(x) >= 3 and len(y) >= 3:
                        all_shapes.append([x_px, y_px])
                except ValueError:
                    break
                if i % 10 == 0 or i == total:
                    percent = int(i / total * 100)
                    progress_dialog.setValue(i)
                    progress_dialog.setLabelText(f"Loading shapes... {percent}% loaded")
                    QApplication.processEvents()
                if progress_dialog.wasCanceled():
                    all_shapes = []  # Discard all loaded shapes if cancelled
                    break

            # Downscale shape size to match image resolution
            for s, shape in enumerate(all_shapes):
                for c, coordinate in enumerate(shape):
                    all_shapes[s][c] = coordinate * self.scale

            for shape_idx, shape in enumerate(all_shapes):
                points = [QPointF(int(x), int(y)) for x, y in zip(*shape)]
                if len(points) >= 3:
                    polygon = Polygon(points, f"Shape_{shape_idx}")
                    if hasattr(shape, "score"):
                        polygon.set_score(shape.score)
                    self.state.shapes.append(polygon)
            self.image_viewer.update_polygon_display()
            progress_dialog.setValue(total)

            # Repaint shapes with the current color (default or user-selected)
            main_window = self.parent()
            while main_window and not hasattr(main_window, "image_viewer"):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, "image_viewer"):
                main_window.image_viewer.update_polygon_display()

        except Exception as e:
            print(f"Error parsing XML: {e}")
            QMessageBox.critical(
                self, "XML Parsing Error", f"Failed to parse XML file:\n{str(e)}"
            )

    def reset_home_buttons(self) -> None:
        assert self.state.state == AppState.HOME
        for button in self.page1.buttons:
            button.setEnabled(False)
        self.page1.add_channel_btn.setEnabled(True)

    def enable_adv_home_buttons(self) -> None:
        assert self.state.state == AppState.ADV_HOME
        for button in self.page1.buttons:
            button.setEnabled(True)

    def reset_main_buttons(self) -> None:
        assert self.state.state == AppState.MAIN
        for button in self.page2.buttons:
            button.setEnabled(False)

        # Check state-dependent buttons
        if self.state.can_add_ar():
            self.page2.add_ar_btn.setEnabled(True)
        self.page2.delete_ar_btn.setEnabled(True)
        if self.state.can_add_lnd():
            self.page2.add_lnd_btn.setEnabled(True)
        if self.state.selected_shape_ids:
            self.page2.export_btn.setEnabled(True)
        if self.state.can_load_ar():
            self.page2.load_ar_btn.setEnabled(True)
        if self.state.can_load_lnd():
            self.page2.load_lnd_btn.setEnabled(True)

        self.page2.delete_lnd_btn.setEnabled(True)
        self.page2.k_box.setEnabled(True)
        self.page2.select_shapes_btn.setEnabled(True)
        self.page2.add_shapes_btn.setEnabled(True)
        self.page2.rem_shapes_btn.setEnabled(True)
        self.page2.back_btn.setEnabled(True)

    def toggle_landmark_selection(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_landmark_selection()
            self.page2.add_lnd_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.delete_last_point_lnd_btn.setEnabled(True)
            self.page2.add_lnd_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.SELECTING_LND
            self.state.cancel_landmark()
            self.page2.add_lnd_btn.setText("Add Landmark")
            self.reset_main_buttons()

    def enable_confirm_landmark(self) -> None:
        self.page2.confirm_lnd_btn.setEnabled(True)

    def disable_confirm_landmark(self) -> None:
        self.page2.confirm_lnd_btn.setEnabled(False)

    def confirm_landmark(self) -> None:
        self.state.confirm_landmark()
        self.page2.add_lnd_btn.setText("Add Landmark")
        self.reset_main_buttons()

    def delete_last_lnd_point(self) -> None:
        self.state.delete_last_lnd_point()

    def toggle_landmark_deletion(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_landmark_deletion()
            self.page2.delete_lnd_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.delete_lnd_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.DELETING_LND
            self.state.end_landmark_deletion()
            self.page2.delete_lnd_btn.setText("Delete Landmark")
            self.reset_main_buttons()

    def toggle_ar_selection(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_ar_selection()
            self.page2.add_ar_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.add_ar_btn.setEnabled(True)
            self.page2.delete_last_point_ar_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.SELECTING_AR
            self.state.cancel_ar()
            self.page2.add_ar_btn.setText("Add AR")
            self.reset_main_buttons()

    def enable_confirm_ar(self, enable: bool = True) -> None:
        self.page2.confirm_ar_btn.setEnabled(enable)

    def enable_filter_ar(self, enable: bool = True) -> None:
        self.page2.filter_ar_btn.setEnabled(enable)

    def confirm_ar(self) -> None:
        self.state.confirm_ar()
        self.page2.add_ar_btn.setText("Add AR")
        self.reset_main_buttons()

    def delete_last_ar_point(self) -> None:
        self.state.delete_last_ar_point()

    def toggle_ar_deletion(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_ar_deletion()
            self.page2.delete_ar_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.delete_ar_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.DELETING_AR
            self.state.end_ar_deletion()
            self.page2.delete_ar_btn.setText("Delete AR")
            self.reset_main_buttons()

    def select_shapes(self) -> None:
        self.state.select_shapes(self.page2.k_box.value())

    def toggle_shape_add(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.state = AppState.ADDING_SHP
            self.page2.add_shapes_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.add_shapes_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.ADDING_SHP
            self.state.state = AppState.MAIN
            self.page2.add_shapes_btn.setText("Add")
            self.reset_main_buttons()

    def toggle_shape_rem(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.state = AppState.DELETING_SHP
            self.page2.rem_shapes_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.rem_shapes_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.DELETING_SHP
            self.state.state = AppState.MAIN
            self.page2.rem_shapes_btn.setText("Delete")
            self.reset_main_buttons()

    def export_selected_shapes(self) -> None:
        """
        Export selected shapes to XML and CSV after prompting for a base file name.
        """
        # Prompt for base file name
        base_path, _ = QFileDialog.getSaveFileName(
            self, "Export Selected Shapes", "", "All Files (*)"
        )
        if not base_path:
            return
        # Get selected shape indices
        selected_indices = self.state.selected_shape_ids
        if not selected_indices:
            QMessageBox.warning(
                self, "No Selection", "No shapes are selected for export."
            )
            return
        # Find ImXML instance (assume loaded as self.im_xml)
        if not hasattr(self, "im_xml") or self.im_xml is None:
            QMessageBox.critical(
                self, "Error", "No ImXML instance loaded. Please load shapes first."
            )
            return
        # Export XML
        xml_path = base_path + ".xml"
        self.im_xml.export_xml(xml_path, selected_indices)
        # Export CSV
        csv_path = base_path + ".csv"
        # Get scores from state.shapes
        data = []
        for idx in selected_indices:
            shape = self.state.shapes[idx]
            score = shape.score if hasattr(shape, "score") else None
            data.append({"CellID": idx + 1, "Score": score})
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        QMessageBox.information(
            self, "Export Complete", f"Exported to:\n{xml_path}\n{csv_path}"
        )
        # Export Landmarks XML
        landmarks_path = base_path + "_landmarks.xml"
        self.im_xml.export_landmarks_xml(
            landmarks_path, self.state.landmarks, self.scale
        )
        # Export AR XML
        ar_path = base_path + "_AR.xml"
        self.im_xml.export_ar_xml(ar_path, self.state.active_regions, self.scale)

    # Update after loading landmarks from file
    def load_landmarks_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Landmarks XML", "", "XML Files (*.xml);;All Files (*)"
        )
        if not file_path:
            return
        try:
            tree = etree.parse(file_path)
            root = tree.getroot()
            n_landmarks = int(root.findtext("LandmarkCount", "0"))
            landmarks = []
            for i in range(1, n_landmarks + 1):
                lnd_elem = root.find(f"Landmark_{i}")
                if lnd_elem is not None:
                    point_count = int(lnd_elem.findtext("PointCount", "0"))
                    points = []
                    for j in range(1, point_count + 1):
                        x = int(float(lnd_elem.findtext(f"X_{j}", "0")) * self.scale)
                        y = int(float(lnd_elem.findtext(f"Y_{j}", "0")) * self.scale)
                        points.append(QPointF(x, y))
                    if points:
                        landmarks.append(points)
            if len(landmarks) > 2:
                QMessageBox.warning(
                    self, "Error", "Landmark file contains more than two shapes."
                )
                return
            self.state.landmarks = landmarks
            self.image_viewer.landmark_items.clear()
            for lnd in landmarks:
                self.image_viewer.add_persistent_lnd(lnd)
            if len(landmarks) == 2:
                self.state.set_scores()

            self.reset_main_buttons()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load landmarks: {e}")

    def load_ar_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load AR XML", "", "XML Files (*.xml);;All Files (*)"
        )
        if not file_path:
            return
        try:
            tree = etree.parse(file_path)
            root = tree.getroot()
            n_ars = int(root.findtext("ARCount", "0"))
            ars = []
            for i in range(1, n_ars + 1):
                ar_elem = root.find(f"AR_{i}")
                if ar_elem is not None:
                    point_count = int(ar_elem.findtext("PointCount", "0"))
                    points = []
                    for j in range(1, point_count + 1):
                        x = int(float(ar_elem.findtext(f"X_{j}", "0")) * self.scale)
                        y = int(float(ar_elem.findtext(f"Y_{j}", "0")) * self.scale)
                        points.append(QPointF(x, y))
                    if points:
                        ars.append(points)
            self.state.active_regions = ars
            self.image_viewer.ar_items.clear()
            for ar in ars:
                self.image_viewer.add_persistent_ar(ar)
            self.state.filter_by_ar()
            self.reset_main_buttons()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load ARs: {e}")

    # Call these in MainWindow methods that add/remove landmarks/ARs:
    def confirm_landmark(self) -> None:
        self.state.confirm_landmark()
        self.page2.add_lnd_btn.setText("Add Landmark")
        self.reset_main_buttons()

    def toggle_landmark_deletion(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_landmark_deletion()
            self.page2.delete_lnd_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.delete_lnd_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.DELETING_LND
            self.state.end_landmark_deletion()
            self.page2.delete_lnd_btn.setText("Delete Landmark")
            self.reset_main_buttons()

    def confirm_ar(self) -> None:
        self.state.confirm_ar()
        self.page2.add_ar_btn.setText("Add AR")
        self.reset_main_buttons()

    def toggle_ar_deletion(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_ar_deletion()
            self.page2.delete_ar_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.delete_ar_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.DELETING_AR
            self.state.end_ar_deletion()
            self.page2.delete_ar_btn.setText("Delete AR")
            self.reset_main_buttons()
