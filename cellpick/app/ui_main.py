import math
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional

import lxml.etree as etree
import numpy as np
from scipy import interpolate
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
    QDialog,
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

from .components import CHANNEL_COLORS, AppState, AppStateManager, DataLoadMode, Polygon
from .image_viewer import ImageViewer
from .ui_components import (
    AnimatedButton,
    ClickableColorLabel,
    ClickableLabel,
    ProgressDialog,
)
from .utils import (
    ImXML,
    DVPXML,
    MockDVPXML,
    export_xml,
    export_landmarks_xml,
    export_ar_xml,
)
from .spatialdata_io import (
    SpatialDataLoader,
    SpatialDataExporter,
    SPATIALDATA_AVAILABLE,
)

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
    add_spatialdata_btn: AnimatedButton
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
        button_panel1 = QGroupBox("Load Data")
        button_layout1 = QVBoxLayout(button_panel1)
        button_panel2 = QGroupBox("Image Adjustments")
        button_layout2 = QVBoxLayout(button_panel2)
        button_panel3 = QGroupBox("Calibration")
        button_layout3 = QVBoxLayout(button_panel3)
        self.add_spatialdata_btn = AnimatedButton("Add spatial data")
        self.add_channel_btn = AnimatedButton("Add channel")
        self.load_shapes_btn = AnimatedButton("Load shapes")
        self.load_labels_btn = AnimatedButton("Load labels")
        self.load_calibration_btn = AnimatedButton("Load File", size=(30, 96))
        self.manual_calibration_btn = AnimatedButton("Manual", size=(30, 96))
        self.confirm_calibration_btn = AnimatedButton("Calibrate")
        self.select_shape_color_btn = AnimatedButton("Select shape color")
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
        button_layout1.addWidget(self.add_spatialdata_btn)
        button_layout1.addWidget(self.add_channel_btn)
        button_layout1.addWidget(self.channel_control_panel)
        button_layout1.addWidget(self.load_shapes_btn)
        button_layout1.addWidget(self.load_labels_btn)
        button_layout2.addWidget(QLabel("Brightness"))
        button_layout2.addWidget(self.gamma_slider)
        button_layout2.addWidget(QLabel("Contrast"))
        button_layout2.addWidget(self.contrast_slider)
        button_layout2.addWidget(self.refresh_btn)
        button_layout2.addWidget(self.select_shape_color_btn)

        subwidget1 = QWidget()
        sublayout1 = QHBoxLayout(subwidget1)
        sublayout1.setContentsMargins(0, 0, 0, 0)
        sublayout1.setSpacing(8)
        sublayout1.addWidget(self.load_calibration_btn)
        sublayout1.addWidget(self.manual_calibration_btn)
        button_layout3.addWidget(subwidget1)
        button_layout3.addWidget(self.confirm_calibration_btn)

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
    export_spatialdata_btn: AnimatedButton
    load_lnd_btn: AnimatedButton
    load_ar_btn: AnimatedButton
    clustering_type: QComboBox
    #label_checkboxes_container: QWidget
    label_checkboxes: dict
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
        self.delete_last_point_lnd_btn = AnimatedButton("Undo", size=(30, 96))
        self.confirm_lnd_btn = AnimatedButton("Confirm", size=(30, 96))
        self.cancel_lnd_btn = AnimatedButton("Cancel")
        self.delete_lnd_btn = AnimatedButton("Delete Landmark")
        self.add_ar_btn = AnimatedButton("Add AR")
        self.delete_last_point_ar_btn = AnimatedButton("Undo", size=(30, 96))
        self.confirm_ar_btn = AnimatedButton("Confirm", size=(30, 96))
        self.delete_ar_btn = AnimatedButton("Delete AR")
        self.select_shapes_btn = AnimatedButton("Automatic Selection")
        self.k_box = QSpinBox()
        self.k_box.setMinimum(0)
        self.k_box.setMaximum(10000)
        self.clustering_type = QComboBox()
        self.clustering_type.addItems(
            ["Select k over union of regions", "Random", "Select k per region"]
        )
        self.label_checkboxes = {}
        # Container for label checkboxes (initially hidden)
        #self.label_checkboxes_container = QWidget()
        # self.label_checkboxes_layout = QVBoxLayout(self.label_checkboxes_container)
        # self.label_checkboxes_layout.setContentsMargins(0, 0, 0, 0)
        self.label_checkboxes_container = ScrollableContainer(height=60)
        self.label_checkboxes_layout = self.label_checkboxes_container.inner_layout
        self.label_checkboxes_container.hide()

        self.add_shapes_btn = AnimatedButton("Add", size=(30, 96))
        self.rem_shapes_btn = AnimatedButton("Delete", size=(30, 96))
        self.export_btn = AnimatedButton(
            "Export as XML",
            color1="34, 197, 94",
            color2="21, 128, 61",
        )
        self.export_spatialdata_btn = AnimatedButton(
            "Export to Spatial Data",
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
        # Add label checkboxes container
        button_layout3.addWidget(self.label_checkboxes_container)
        button_layout3.addWidget(self.select_shapes_btn)

        subwidget3 = QWidget()
        sublayout3 = QHBoxLayout(subwidget3)
        sublayout3.setContentsMargins(0, 0, 0, 0)
        sublayout3.setSpacing(8)
        sublayout3.addWidget(self.add_shapes_btn)
        sublayout3.addWidget(self.rem_shapes_btn)
        button_layout3.addWidget(subwidget3)

        button_panel4 = QGroupBox("Export Results")
        button_layout4 = QVBoxLayout(button_panel4)
        button_layout4.addWidget(self.export_btn)
        button_layout4.addWidget(self.export_spatialdata_btn)

        layout.addWidget(button_panel2)
        layout.addWidget(button_panel1)
        layout.addWidget(button_panel3)
        layout.addWidget(button_panel4)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addWidget(self.back_btn)
        self.buttons = self.findChildren(AnimatedButton)

    def update_label_checkboxes(self, labels: dict) -> None:
        """
        Update the label checkboxes based on loaded labels.

        Parameters
        ----------
        labels : dict
            Dictionary mapping label values to RGB colors (RGB 0-255 tuples)
        """
        # Clear existing checkboxes
        for checkbox in self.label_checkboxes.values():
            checkbox.deleteLater()
        self.label_checkboxes.clear()
        for i in range(self.label_checkboxes_layout.count()):
            self.label_checkboxes_layout.itemAt(i).widget().deleteLater()

        if labels is None:
            # Remove "Select k per label" option to clustering type if present
            if self.clustering_type.count() == 4: 
                self.clustering_type.removeItem(3)
            return

        # Create new checkboxes for each label with color indicator
        for label in sorted(labels.keys()):
            # Create a container widget for checkbox + color indicator
            container = QWidget()
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(6)

            checkbox = QCheckBox(str(label))
            checkbox.setChecked(True)  # All selected by default

            # Create color indicator (small colored square)
            color_label = QLabel()
            color_label.setFixedSize(16, 16)
            rgb = labels[label]
            color_label.setStyleSheet(
                f"background-color: rgb({int(rgb[0])}, {int(rgb[1])}, {int(rgb[2])}); "
                f"border: 1px solid #666; border-radius: 2px;"
            )

            h_layout.addWidget(color_label)
            h_layout.addWidget(checkbox)
            h_layout.addStretch()

            self.label_checkboxes[label] = checkbox
            self.label_checkboxes_layout.addWidget(container)

        # Add "Select k per label" option to clustering type if not already present
        if self.clustering_type.count() == 3:
            self.clustering_type.addItem("Select k per label")

    def get_selected_labels(self) -> Optional[List[Any]]:
        """
        Get list of selected labels from checkboxes.

        Returns
        -------
        Optional[List[Any]]
            List of selected label values, or None if no labels are loaded
        """
        if not self.label_checkboxes:
            return None
        return [
            label
            for label, checkbox in self.label_checkboxes.items()
            if checkbox.isChecked()
        ]

    def show_label_checkboxes(self, show: bool) -> None:
        """
        Show or hide the label checkboxes container.

        Parameters
        ----------
        show : bool
            Whether to show the checkboxes
        """
        if show:
            self.label_checkboxes_container.show()
        else:
            self.label_checkboxes_container.hide()
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
    xml_path, meta_path = None, None

    def __init__(self) -> None:
        super().__init__()
        self.image_resolution = 25000
        self.channels: List[str] = []
        self.state = AppStateManager()
        self.state.main_window = self
        self.setWindowTitle("CellPick")
        # SpatialData-related attributes
        self._spatialdata_loader = None
        self._spatialdata_categorical_columns = []
        self._loaded_spatialdata_path = None
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
        self.page1.load_labels_btn.clicked.connect(self.load_labels)
        self.page1.load_calibration_btn.clicked.connect(self.load_calibration)
        self.page1.manual_calibration_btn.clicked.connect(self.manual_calibration)
        self.page1.confirm_calibration_btn.clicked.connect(self.confirm_calibration)
        self.page1.add_channel_btn.clicked.connect(self.add_channel)
        self.page1.add_spatialdata_btn.clicked.connect(self.add_spatialdata)
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
        self.page2.export_spatialdata_btn.clicked.connect(self.export_to_spatialdata)
        self.page2.load_lnd_btn.clicked.connect(self.load_landmarks_from_file)
        self.page2.load_ar_btn.clicked.connect(self.load_ar_from_file)
        self.page2.clustering_type.currentIndexChanged.connect(
            self.on_clustering_type_changed
        )
        self.reset_home_buttons()
        self.state.state = AppState.MAIN
        self.reset_main_buttons()
        self.state.state = AppState.HOME
        self.shape_outline_color = QColor(255, 255, 255)

    def goto_first_page(self) -> None:
        self.state.state = AppState.ADV_HOME
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

    def set_image_workflow_mode(self) -> None:
        """
        Set the app to IMAGE workflow mode and disable SpatialData buttons.
        This is irreversible without restarting the app.
        """
        self.state.data_load_mode = DataLoadMode.IMAGE

    def set_spatialdata_workflow_mode(self) -> None:
        """
        Set the app to SPATIALDATA workflow mode and disable IMAGE workflow buttons.
        This is irreversible without restarting the app.
        """
        self.state.data_load_mode = DataLoadMode.SPATIALDATA
        

    def add_channel(self) -> None:
        # Check if we're already in SPATIALDATA mode
        if self.state.data_load_mode == DataLoadMode.SPATIALDATA:
            QMessageBox.warning(
                self,
                "Wrong Workflow",
                "Cannot add image channels in SpatialData workflow mode.\n"
                "Please restart the application to switch workflows.",
            )
            return

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
            image_data = np.moveaxis(image_data, ch_idx, -1)  # now it's (H, W, C)

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
                
                self.img_stack.setCurrentWidget(self.image_viewer)

                # Set IMAGE workflow mode on first channel load
                if self.state.data_load_mode == DataLoadMode.NONE:
                    self.set_image_workflow_mode()
                
                self.state.enable_advanced_home()
                # Disable calibration buttons until shapes are loaded
                self.page1.load_calibration_btn.setEnabled(False)
                self.page1.manual_calibration_btn.setEnabled(False)
                self.page1.confirm_calibration_btn.setEnabled(False)

    def add_spatialdata(self) -> None:
        """Load data from a SpatialData .zarr store."""
        # Check if we're already in IMAGE mode
        if self.state.data_load_mode == DataLoadMode.IMAGE:
            QMessageBox.warning(
                self,
                "Wrong Workflow",
                "Cannot load SpatialData in image workflow mode.\n"
                "Please restart the application to switch workflows.",
            )
            return

        if not SPATIALDATA_AVAILABLE:
            QMessageBox.critical(
                self,
                "SpatialData Not Available",
                "SpatialData is not installed. Please install it with:\n"
                "pip install spatialdata spatialdata-io spatialdata-plot",
            )
            return

        # Open folder dialog for .sdata or .zarr
        zarr_path = QFileDialog.getExistingDirectory(
            self,
            "Select SpatialData Folder (.sdata or .zarr)",
            "",
            QFileDialog.ShowDirsOnly,
        )

        if not zarr_path:
            return

        try:
            # Load SpatialData
            progress = QProgressDialog("Loading SpatialData...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.ApplicationModal)
            progress.setValue(10)
            QApplication.processEvents()

            loader = SpatialDataLoader(zarr_path)
            # Store the loader for later use (e.g., loading labels)
            self.spatial_data_loader = loader
            progress.setValue(20)
            QApplication.processEvents()

            # Check what's available
            available_images = loader.get_available_images()
            available_labels = loader.get_available_labels()
            available_shapes = loader.get_available_shapes()

            if not available_images and not available_labels and not available_shapes:
                QMessageBox.warning(
                    self,
                    "No Data Found",
                    "The selected SpatialData store contains no images, labels, or shapes.",
                )
                progress.close()
                return

            # Load images
            if available_images:
                progress.setLabelText("Extracting image channels...")
                progress.setValue(30)
                QApplication.processEvents()

                channels, channel_names = loader.extract_image_channels()

                # Downsample if needed
                inv_scale = 1  # Track downsampling factor for coordinates
                if channels:
                    height, width = channels[0].shape
                    max_side = max(height, width)

                    if max_side > self.image_resolution:
                        inv_scale = math.ceil(max_side / self.image_resolution)
                        self.scale /= inv_scale

                        downsampled_channels = []
                        for ch in channels:
                            downsampled = ch[::inv_scale, ::inv_scale].copy()
                            downsampled_channels.append(downsampled)
                        channels = downsampled_channels

                    progress.setValue(50)
                    QApplication.processEvents()

                    # Add channels to viewer
                    for i, (channel_data, channel_name) in enumerate(
                        zip(channels, channel_names)
                    ):
                        # Use default white color for all channels
                        custom_color = np.array([255, 255, 255])

                        error_id = self.image_viewer.add_channel(
                            channel_data, channel_name, custom_color
                        )
                        if error_id != 0:
                            QMessageBox.warning(
                                self, "Error", f"Failed to add channel {channel_name}"
                            )
                            continue

                        self.channels.append(zarr_path)
                        self.add_channel_control(
                            channel_name, len(self.image_viewer.channels) - 1
                        )

                    self.img_stack.setCurrentWidget(self.image_viewer)

            progress.setValue(60)
            QApplication.processEvents()

            # Load shapes from labels or shapes
            polygons_loaded = False

            if available_labels:
                progress.setLabelText("Extracting polygons from segmentation masks...")
                progress.setValue(70)
                QApplication.processEvents()

                # Define progress callback to update the dialog
                def update_polygon_progress(current, total):
                    if progress.wasCanceled():
                        raise RuntimeError("Operation cancelled by user")
                    percent = 70 + int(15 * current / total)
                    progress.setValue(percent)
                    progress.setLabelText(
                        f"Extracting polygons: {current}/{total} cells..."
                    )
                    QApplication.processEvents()

                polygons = loader.extract_polygons_from_labels(
                    max_cells=100000, progress_callback=update_polygon_progress
                )

                if polygons:
                    self.state.reset_shapes()
                    for item in polygons:
                        if len(item) == 3:
                            points, label, original_id = item
                            polygon = Polygon(points, label, original_id=original_id)
                        else:
                            # Fallback for old format
                            points, label = item
                            polygon = Polygon(points, label)
                        self.state.shapes.append(polygon)
                    polygons_loaded = True

                progress.setValue(85)
                QApplication.processEvents()

            elif available_shapes:
                progress.setLabelText("Extracting polygons from shapes...")
                progress.setValue(70)
                QApplication.processEvents()

                polygons = loader.extract_polygons_from_shapes()

                if polygons:
                    self.state.reset_shapes()
                    for points, label in polygons:
                        polygon = Polygon(points, label)
                        self.state.shapes.append(polygon)
                    polygons_loaded = True

                progress.setValue(85)
                QApplication.processEvents()

            # Update display
            if polygons_loaded:
                self.image_viewer.update_polygon_display()

            # Check for and load CellPick annotations
            annotations_loaded = []
            if loader.has_cellpick_annotations():
                progress.setLabelText("Loading CellPick annotations...")
                progress.setValue(90)
                QApplication.processEvents()

                # Load landmarks first (they don't affect other selections)
                landmarks = loader.load_cellpick_landmarks()
                if landmarks:
                    self.state.landmarks = landmarks
                    # Add landmarks to visual display
                    for landmark_points in landmarks:
                        self.image_viewer.add_persistent_lnd(landmark_points)
                    annotations_loaded.append(f"{len(landmarks)} landmark(s)")

                    # If 2 landmarks loaded, set scores just like manual selection
                    if len(landmarks) == 2:
                        self.state.set_scores()

                # Load active regions (they determine which cells are active)
                active_regions = loader.load_cellpick_active_regions()
                if active_regions:
                    self.state.active_regions = active_regions
                    # Add active regions to visual display
                    for ar_points in active_regions:
                        self.image_viewer.add_persistent_ar(ar_points)
                    annotations_loaded.append(f"{len(active_regions)} active region(s)")

                    # Update active shapes based on loaded ARs (but don't set selected yet)
                    self.state.active_shape_ids = []
                    for i in range(len(self.state.shapes)):
                        c = self.state.shapes[i].centroid()
                        is_contained = False
                        for ar in self.state.active_regions:
                            poly = QPolygonF(ar)
                            if poly.containsPoint(c, Qt.OddEvenFill):
                                is_contained = True
                                break
                        if is_contained:
                            self.state.active_shape_ids.append(i)

                # Load selected cells AFTER ARs are processed
                if polygons_loaded:
                    # Create list of (points, label) tuples for matching
                    all_polygons = [
                        (poly.points, poly.label) for poly in self.state.shapes
                    ]
                    selected_ids = loader.load_cellpick_selected_cells(all_polygons)
                    if selected_ids:
                        self.state.selected_shape_ids = selected_ids
                        annotations_loaded.append(
                            f"{len(selected_ids)} selected cell(s)"
                        )
                    elif active_regions:
                        # If no selected cells but we have ARs, default to all active shapes
                        self.state.selected_shape_ids = self.state.active_shape_ids

                # Update display
                self.image_viewer.update_polygon_display()

            # Create a MockDVPXML for XML export compatibility
            if polygons_loaded:
                self.im_xml = MockDVPXML(self.state.shapes)

            # Store the loader for table access
            self._spatialdata_loader = loader

            # Store the path for later export
            self._loaded_spatialdata_path = zarr_path

            # Get categorical columns for label-based selection
            categorical_columns = loader.get_categorical_columns()
            if categorical_columns:
                # Store categorical columns for later use
                self._spatialdata_categorical_columns = categorical_columns
                # Update clustering dropdown to include label options
                # self.update_clustering_dropdown_with_labels(categorical_columns)
            else:
                self._spatialdata_categorical_columns = []

            progress.setValue(100)
            progress.close()

            # Set SPATIALDATA workflow mode
            if self.state.data_load_mode == DataLoadMode.NONE:
                self.set_spatialdata_workflow_mode()
            
            self.state.enable_advanced_home()

            # Build success message
            msg = f"Successfully loaded:\n"
            msg += f"- {len(self.image_viewer.channels)} image channel(s)\n"
            msg += f"- {len(self.state.shapes)} cell polygon(s)"
            if annotations_loaded:
                msg += f"\n\nCellPick annotations:\n- " + "\n- ".join(
                    annotations_loaded
                )

            QMessageBox.information(self, "SpatialData Loaded", msg)

        except RuntimeError as e:
            # User cancelled
            if "progress" in locals():
                progress.close()
            if "cancelled" in str(e).lower():
                return  # Silent cancellation
            QMessageBox.warning(
                self, "Operation Cancelled", "SpatialData loading was cancelled."
            )
        except Exception as e:
            if "progress" in locals():
                progress.close()
            QMessageBox.critical(
                self,
                "Error Loading SpatialData",
                f"Failed to load SpatialData:\n{str(e)}",
            )

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
        if not self.image_viewer.channels:
            QMessageBox.warning(self, "Warning", "Please load an image first")
            return

        xml_path, _ = QFileDialog.getOpenFileName(
            self, "Open XML containing shapes", "", "XML Files (*.xml);;All Files (*)"
        )
        if not xml_path:
            return
        self.xml_path = xml_path

        # Enable calibration buttons now that shapes are loaded
        self.page1.load_calibration_btn.setEnabled(True)
        self.page1.manual_calibration_btn.setEnabled(True)
        self.page1.confirm_calibration_btn.setEnabled(True)

        # Show informative message
        QMessageBox.information(
            self,
            "Shapes Loaded",
            "Shape file has been successfully loaded!\n\n"
            "To display the shapes on the image, please calibrate using one of the following methods:\n\n"
            "• Load Calibration File: Use an existing calibration metadata file\n"
            "• Manual Calibration: Define three calibration points manually\n\n"
            "After selecting your calibration method, click 'Calibrate' to proceed.",
        )

    def load_calibration(self) -> None:
        assert(self.state.data_load_mode == DataLoadMode.IMAGE)
        self.state.calibration_points = []
        self.state.image_viewer.remove_calibration_items()
        if not self.image_viewer.channels:
            QMessageBox.warning(self, "Warning", "Please load an image first")
            return

        meta_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image Metadata File", "", "TXT Files (*.txt);;All Files (*)"
        )
        if not meta_path:
            return
        self.meta_path = meta_path

    def manual_calibration(self) -> None:
        assert(self.state.data_load_mode == DataLoadMode.IMAGE)
        self.meta_path = None
        if self.state.state == AppState.ADV_HOME:
            self.state.start_calibration_selection()
            self.page1.manual_calibration_btn.setText("Cancel")
            for button in self.page1.buttons:
                button.setEnabled(False)
            self.page1.manual_calibration_btn.setEnabled(True)
        else:
            assert (
                self.state.state == AppState.SELECTING_CLB
            ), f"State: {self.state.state}"
            self.state.end_calibration_selection()
            self.page1.manual_calibration_btn.setText("Manual")
            self.enable_adv_home_buttons()

    def confirm_calibration(self):
        if self.meta_path is not None:
            self.load_shapes_and_load_calibrate()
        if len(self.state.calibration_points) == 3:
            self.load_shapes_and_manual_calibrate()

    def load_shapes_and_manual_calibrate(self) -> None:
        xml_path = self.xml_path

        try:
            dvpxml = DVPXML(xml_path)
            self.im_xml = dvpxml

            xx = np.array([pt.x() for pt in self.state.calibration_points])
            yy = np.array([pt.y() for pt in self.state.calibration_points])
            fxx = interpolate.interp1d(
                dvpxml.y_calibration, xx, fill_value="extrapolate"
            )
            fyy = interpolate.interp1d(
                dvpxml.x_calibration, yy, fill_value="extrapolate"
            )
            self.state.reset_shapes()
            total = dvpxml.n_shapes
            progress_dialog = QProgressDialog(
                "Loading shapes...", "Cancel", 0, total, self
            )
            progress_dialog.setWindowModality(Qt.ApplicationModal)
            progress_dialog.setValue(0)
            progress_dialog.show()
            all_shapes = []
            for i in range(1, total + 1):
                try:
                    x, y = dvpxml.return_shape(i)
                    x_px = fxx(y)
                    y_px = fyy(x)
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

            # Downscaling shape size to match image resolution is not needed for manual

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

    def load_shapes_and_load_calibrate(self) -> None:
        meta_path = self.meta_path
        xml_path = self.xml_path
        try:
            meta = pd.read_csv(meta_path, sep="\t")
            calibration = meta.iloc[0, 0]
            im_xml = ImXML(meta_path, xml_path, "")
            self.im_xml = im_xml.dvpxml
            im_xml.im_shape = self.image_viewer.channels[0].image_data.shape
            im_xml.calibration(calibration)
            self.state.reset_shapes()
            total = im_xml.dvpxml.n_shapes
            progress_dialog = QProgressDialog(
                "Loading shapes...", "Cancel", 0, total, self
            )
            progress_dialog.setWindowModality(Qt.ApplicationModal)
            progress_dialog.setValue(0)
            progress_dialog.show()
            all_shapes = []
            for i in range(1, total + 1):
                try:
                    x, y = im_xml.dvpxml.return_shape(i)
                    x_px = im_xml.fxx(y)
                    y_px = im_xml.fyy(x)
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

    def load_labels(self) -> None:
        """Load cell labels from CSV or SpatialData table."""
        from .ui_components import LoadLabelsDialog

        # Check if shapes are loaded
        if not self.state.shapes:
            QMessageBox.warning(self, "No Shapes", "Please load cell shapes first.")
            return

        # Get the SpatialDataLoader if one exists
        spatial_data_loader = getattr(self, "spatial_data_loader", None)

        # Open dialog
        dialog = LoadLabelsDialog(spatial_data_loader, self)
        if dialog.exec() != QDialog.Accepted:
            return

        # Load labels based on selected source
        labels_dict = None
        delete_labels = False
        if dialog.selected_source == "csv":
            from .spatialdata_io import SpatialDataLoader

            labels_dict = SpatialDataLoader.load_labels_from_csv(dialog.csv_path)
            if labels_dict is None:
                QMessageBox.critical(
                    self, "Error", "Failed to load labels from CSV file."
                )
                return
        elif dialog.selected_source == "spatialdata":
            if spatial_data_loader:
                labels_dict = spatial_data_loader.get_cell_labels(
                    dialog.column_name,
                    dialog.table_name,
                    instance_column=getattr(dialog, "id_column", None),
                )
                if labels_dict is None:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to load labels from table '{dialog.table_name}'.",
                    )
                    return
            else:
                QMessageBox.warning(
                    self, "No SpatialData", "No SpatialData file is loaded."
                )
                return
        elif dialog.selected_source == "delete":
            delete_labels = True

        # Load labels into state
        if labels_dict:
            self.state.load_cell_labels(labels_dict)
            # Update label checkboxes in UI
            self.page2.update_label_checkboxes(self.state.label_colors)
            QMessageBox.information(
                self,
                "Success",
                f"Loaded labels for {len(labels_dict)} cells.",
            )
        
        if delete_labels:
            self.state.clear_cell_labels()
            self.page2.update_label_checkboxes(self.state.label_colors)

    def reset_home_buttons(self) -> None:
        assert self.state.state == AppState.HOME
        for button in self.page1.buttons:
            button.setEnabled(False)
        self.page1.add_channel_btn.setEnabled(True)
        self.page1.add_spatialdata_btn.setEnabled(True)

    def enable_adv_home_buttons(self) -> None:
        assert self.state.state == AppState.ADV_HOME
        for button in self.page1.buttons:
            button.setEnabled(True)
        
        if self.state.data_load_mode == DataLoadMode.IMAGE:
            # Disable SpatialData button
            self.page1.add_spatialdata_btn.setEnabled(False)
        else:
            assert(self.state.data_load_mode == DataLoadMode.SPATIALDATA)
            # Disable all IMAGE workflow buttons
            self.page1.add_channel_btn.setEnabled(False)
            self.page1.select_shape_color_btn.setEnabled(True)
            self.page1.load_calibration_btn.setEnabled(False)
            self.page1.manual_calibration_btn.setEnabled(False)
            self.page1.confirm_calibration_btn.setEnabled(False)
            self.page1.load_shapes_btn.setEnabled(False)


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
            if SPATIALDATA_AVAILABLE:
                self.page2.export_spatialdata_btn.setEnabled(True)
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

        self.page2.clustering_type.setEnabled(True)
        self.page2.k_box.setEnabled(True)

    def toggle_landmark_selection(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.start_landmark_selection()
            self.page2.add_lnd_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.delete_last_point_lnd_btn.setEnabled(True)
            self.page2.add_lnd_btn.setEnabled(True)
            self.page2.clustering_type.setEnabled(False)
            self.page2.k_box.setEnabled(False)
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
            self.page2.clustering_type.setEnabled(False)
            self.page2.k_box.setEnabled(False)
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
            self.page2.clustering_type.setEnabled(False)
            self.page2.k_box.setEnabled(False)
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
            self.page2.clustering_type.setEnabled(False)
            self.page2.k_box.setEnabled(False)
        else:
            assert self.state.state == AppState.DELETING_AR
            self.state.end_ar_deletion()
            self.page2.delete_ar_btn.setText("Delete AR")
            self.reset_main_buttons()

    def update_clustering_dropdown_with_labels(
        self, categorical_columns: List[str]
    ) -> None:
        """
        Update the clustering type dropdown to include label-based grouping options.

        Parameters
        ----------
        categorical_columns : List[str]
            List of categorical column names from the spatial data table.
        """
        # Store original items
        original_items = ["Select k over union of regions", "Select k per region"]

        # Clear and re-add items
        self.page2.clustering_type.clear()
        self.page2.clustering_type.addItems(original_items)

        # Add label-based options for each categorical column
        for col in categorical_columns:
            self.page2.clustering_type.addItem(f"Select k per label: {col}")

    def select_shapes(self) -> None:
        self.state.select_shapes(self.page2.k_box.value())

    def on_clustering_type_changed(self, index: int) -> None:
        """
        Handle clustering type selection changes.
        Show label checkboxes when 'Select k per label' is selected.

        Parameters
        ----------
        index : int
            Index of the selected clustering type
        """
        # Show checkboxes only if "Select k per label" is selected (index 2)
        if index == 3 and self.page2.label_checkboxes:
            self.page2.show_label_checkboxes(True)
        else:
            self.page2.show_label_checkboxes(False)

    def toggle_shape_add(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.state = AppState.ADDING_SHP
            self.page2.add_shapes_btn.setText("Cancel")
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.add_shapes_btn.setEnabled(True)
            self.page2.clustering_type.setEnabled(False)
            self.page2.k_box.setEnabled(False)
        else:
            assert self.state.state == AppState.ADDING_SHP
            self.state.state = AppState.MAIN
            self.page2.add_shapes_btn.setText("Add")
            self.reset_main_buttons()

    def toggle_shape_rem(self) -> None:
        if self.state.state == AppState.MAIN:
            self.state.state = AppState.DELETING_SHP
            self.page2.rem_shapes_btn.setText("Cancel")
            self.page2.clustering_type.setEnabled(False)
            self.page2.k_box.setEnabled(False)
            for button in self.page2.buttons:
                button.setEnabled(False)
            self.page2.rem_shapes_btn.setEnabled(True)
        else:
            assert self.state.state == AppState.DELETING_SHP
            self.state.state = AppState.MAIN
            self.page2.rem_shapes_btn.setText("Delete")
            self.reset_main_buttons()

    def export_to_spatialdata(self) -> None:
        """
        Export CellPick annotations to SpatialData format.
        """
        if not SPATIALDATA_AVAILABLE:
            QMessageBox.critical(
                self,
                "SpatialData Not Available",
                "SpatialData is not installed. Please install it with:\n"
                "pip install spatialdata spatialdata-io spatialdata-plot",
            )
            return

        # Check if we have anything to export
        has_selection = len(self.state.selected_shape_ids) > 0
        has_landmarks = len(self.state.landmarks) > 0
        has_ar = len(self.state.active_regions) > 0

        if not (has_selection or has_landmarks or has_ar):
            QMessageBox.warning(
                self,
                "Nothing to Export",
                "No selections, landmarks, or active regions to export.",
            )
            return

        # Prompt for output folder
        output_path = QFileDialog.getSaveFileName(
            self, "Save SpatialData", "", "SpatialData Store (*.sdata)"
        )[0]

        if not output_path:
            return

        # Ensure .sdata extension
        if not output_path.endswith(".sdata") and not output_path.endswith(".zarr"):
            output_path += ".sdata"

        try:
            progress = QProgressDialog(
                "Exporting to SpatialData...", "Cancel", 0, 100, self
            )
            progress.setWindowModality(Qt.ApplicationModal)
            progress.setValue(10)
            QApplication.processEvents()

            # Get selected polygons
            selected_polygons = (
                [self.state.shapes[idx] for idx in self.state.selected_shape_ids]
                if has_selection
                else []
            )

            # Get image shape and channels
            image_shape = None
            image_channels = None
            all_polygons = None

            if self.image_viewer.channels:
                image_shape = self.image_viewer.channels[0].image_data.shape

                # If in IMAGE mode, prepare channels and all polygons for export
                if self.state.data_load_mode == DataLoadMode.IMAGE:
                    image_channels = [
                        (ch.image_data, ch.name) for ch in self.image_viewer.channels
                    ]
                    # Include ALL shapes for segmentation mask
                    all_polygons = self.state.shapes

            # Get input path if we loaded from SpatialData
            input_path = getattr(self, "_loaded_spatialdata_path", None)

            # Don't use input_path in IMAGE mode (create from scratch)
            if self.state.data_load_mode == DataLoadMode.IMAGE:
                input_path = None

            progress.setValue(30)
            QApplication.processEvents()

            # Define progress callback
            def update_export_progress(message, percent):
                if progress.wasCanceled():
                    raise RuntimeError("Export cancelled by user")
                progress.setLabelText(message)
                progress.setValue(percent)
                QApplication.processEvents()

            # Export to SpatialData
            SpatialDataExporter.export_to_spatialdata(
                input_path=input_path,
                output_path=output_path,
                selected_polygons=selected_polygons,
                landmarks=self.state.landmarks if has_landmarks else None,
                active_regions=self.state.active_regions if has_ar else None,
                image_shape=image_shape,
                coordinate_system="global",
                progress_callback=update_export_progress,
                image_channels=image_channels,
                all_polygons=all_polygons,
            )

            progress.setValue(100)
            progress.close()

            # Build export message
            msg_parts = []
            if has_selection:
                msg_parts.append(f"{len(selected_polygons)} selected cell(s)")
            if has_landmarks:
                msg_parts.append(f"{len(self.state.landmarks)} landmark(s)")
            if has_ar:
                msg_parts.append(f"{len(self.state.active_regions)} active region(s)")

            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported to:\n{output_path}\n\n"
                f"Exported:\n- " + "\n- ".join(msg_parts),
            )

        except Exception as e:
            if "progress" in locals():
                progress.close()
            QMessageBox.critical(
                self, "Export Error", f"Failed to export to SpatialData:\n{str(e)}"
            )

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
        export_xml(xml_path, selected_indices, self.im_xml)
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

        # Export Landmarks XML
        landmarks_path = base_path + "_landmarks.xml"
        export_landmarks_xml(landmarks_path, self.state.landmarks, self.scale)
        # Export AR XML
        ar_path = base_path + "_AR.xml"
        export_ar_xml(ar_path, self.state.active_regions, self.scale)

        QMessageBox.information(
            self, "Export Complete", f"Exported to:\n{xml_path}\n{csv_path}"
        )

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

