"""
apps/media_converter/ui/image_tools_window.py
─────────────────────────────────────────────
Ventana unificada y moderna para MediaHub Image Tools.
Integra:
  1. Quitar Fondo (rembg con modelos u2net, isnet, silueta y pre-carga segura)
  2. Mejorar Calidad 4x (Real-ESRGAN con IA y botones circulares 1-2-3-4)
  3. Marca de Agua Avanzada (Texto o Logo, selector de color, modos Posición X-Y y Mosaicos
     Diagonal/Horizontal/Vertical, dirección/ángulo, tamaño, espaciado de letras y separación)
  4. Optimizador / Compresor Web (JPG, PNG, WebP con control de peso)
Incluye SplitPreview (Antes/Después interactivo) y separación explícita entre "Procesar Imagen"
y "Guardar" (guardando siempre una copia sin modificar el archivo original).
"""

import os
import sys
import shutil
import tempfile
import threading
from PIL import Image
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog, QMessageBox, QComboBox, QCheckBox,
    QSpinBox, QSlider, QProgressBar, QFrame, QLineEdit, QButtonGroup,
    QColorDialog
)
from PyQt6.QtGui import QIcon, QPixmap, QColor, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from apps.media_converter.converters.conversion import (
    BackgroundRemoverLogic,
    ImageEnhancerLogic,
    WatermarkLogic,
    ImageFormats,
)
from apps.media_converter.ui.split_preview import SplitPreviewWidget
from apps.media_converter.i18n import t
from core.sound_manager import SoundManager


def get_asset(filename):
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    p = os.path.join(base, "assets", "hub", filename)
    if os.path.isfile(p):
        return p
    return os.path.join(base, "assets", filename)


def pil_to_qpixmap(pil_img: Image.Image) -> QPixmap:
    """Convierte una imagen PIL RGBA en QPixmap de forma rápida y segura."""
    rgba = pil_img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class ImageWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str)  # (mensaje, ruta_salida)
    error = pyqtSignal(str)

    def __init__(self, task_type: str, params: dict, parent=None):
        super().__init__(parent)
        self.task_type = task_type
        self.params = params

    def run(self):
        try:
            self.progress.emit(15, t("status_processing_ia"))
            orig = self.params["orig"]
            dest = self.params["dest"]

            if self.task_type == "bg_remover":
                model = self.params.get("model", "u2net")
                alpha = self.params.get("alpha", False)
                res = BackgroundRemoverLogic.quitar_fondo(orig, dest, model, alpha)
                if "Error" in res:
                    self.error.emit(res)
                else:
                    self.progress.emit(100, "¡Listo!")
                    self.finished.emit(res, dest)

            elif self.task_type == "quality":
                model = self.params.get("model", "realesrgan-x4plus")
                scale = self.params.get("scale", 4)
                use_tta = self.params.get("tta", False)
                res = ImageEnhancerLogic.mejorar_calidad(orig, dest, model, scale, use_tta)
                if "Error" in res:
                    self.error.emit(res)
                else:
                    self.progress.emit(100, "¡Listo!")
                    self.finished.emit(res, dest)

            elif self.task_type == "watermark":
                base_image = Image.open(orig).convert("RGBA")
                result_image = WatermarkLogic.render_watermark_pil(base_image, self.params)

                ext = os.path.splitext(dest)[1].lower()
                os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
                if ext in [".jpg", ".jpeg"]:
                    result_image.convert("RGB").save(dest, quality=95)
                else:
                    result_image.save(dest)

                self.progress.emit(100, "¡Listo!")
                self.finished.emit("Marca de agua aplicada correctamente", dest)

            elif self.task_type == "compress":
                fmt = self.params.get("fmt", "webp")
                quality = self.params.get("quality", 80)
                img = Image.open(orig)
                res = ImageFormats._save_image(img, dest, fmt, quality=quality)
                self.progress.emit(100, "¡Listo!")
                self.finished.emit(res, dest)

        except Exception as e:
            self.error.emit(str(e))


class ImageToolsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.resize(1080, 700)
        self.setMinimumSize(980, 620)

        icon_path = get_asset("Media-Hub.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.current_orig_path: str | None = None
        self.current_dest_path: str | None = None
        self.current_worker: ImageWorker | None = None
        self._preview_pil_cache: Image.Image | None = None
        self._staging_dir = tempfile.mkdtemp(prefix="mediahub_imagetools_")
        self.last_saved_dir: str | None = None

        self.selected_tta_level: int = 4
        self.wm_text_color: str = "#FFFFFF"
        self.current_logo_path: str | None = None

        self._init_ui()
        self._apply_styles()

        # Pre-cargar rembg y sus dependencias en segundo plano para que el primer uso nunca falle
        threading.Thread(target=BackgroundRemoverLogic.prewarm, daemon=True).start()

    def closeEvent(self, event):
        try:
            if self._staging_dir and os.path.exists(self._staging_dir):
                shutil.rmtree(self._staging_dir, ignore_errors=True)
        except Exception:
            pass
        super().closeEvent(event)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── SIDEBAR ──────────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(18, 24, 18, 24)
        sb_layout.setSpacing(10)

        app_title = QLabel(t("header_title"))
        app_title.setObjectName("sidebarTitle")
        app_sub = QLabel(t("header_sub"))
        app_sub.setObjectName("sidebarSubtitle")
        sb_layout.addWidget(app_title)
        sb_layout.addWidget(app_sub)
        sb_layout.addSpacing(15)

        self.nav_buttons = []
        modules = [
            (t("tab_bg"), 0),
            (t("tab_enhance"), 1),
            (t("tab_watermark"), 2),
            (t("tab_compress"), 3),
        ]

        for text, idx in modules:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        self.btn_open_folder = QPushButton(t("btn_open_folder"))
        self.btn_open_folder.setObjectName("navSecondaryBtn")
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_output_dir)
        sb_layout.addWidget(self.btn_open_folder)

        main_layout.addWidget(sidebar)

        # ── CONTENIDO PRINCIPAL ──────────────────────────────────────────────
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        c_layout = QVBoxLayout(content_frame)
        c_layout.setContentsMargins(28, 24, 28, 24)
        c_layout.setSpacing(14)

        # Barra de carga de archivo
        file_box = QFrame()
        file_box.setObjectName("fileBox")
        fb_layout = QHBoxLayout(file_box)
        fb_layout.setContentsMargins(14, 10, 14, 10)

        self.file_label = QLabel(t("drag_drop_prompt"))
        self.file_label.setObjectName("fileLabel")
        fb_layout.addWidget(self.file_label, stretch=1)

        self.btn_select_file = QPushButton(t("btn_select_image"))
        self.btn_select_file.setObjectName("actionBtnPrimary")
        self.btn_select_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_file.clicked.connect(self._pick_file)
        fb_layout.addWidget(self.btn_select_file)

        c_layout.addWidget(file_box)

        # Preview Split
        self.split_preview = SplitPreviewWidget(self)
        c_layout.addWidget(self.split_preview, stretch=1)

        # Barra de Opciones Dinámica (Stacked por herramienta)
        self.options_stack = QStackedWidget()

        # ── Tab 0: Quitar Fondo ──────────────────────────────────────────────
        tab_bg = QWidget()
        t0_layout = QHBoxLayout(tab_bg)
        t0_layout.setContentsMargins(0, 0, 0, 0)
        t0_layout.addWidget(QLabel(t("lbl_model")))
        self.combo_bg_model = QComboBox()
        self.combo_bg_model.addItems([
            "u2net (General / Preciso)",
            "isnet-general-use",
            "u2net_human_seg (Personas)",
            "silueta (Rápido)"
        ])
        t0_layout.addWidget(self.combo_bg_model)
        self.chk_alpha = QCheckBox("Alpha Matting")
        t0_layout.addWidget(self.chk_alpha)
        t0_layout.addStretch()
        self.options_stack.addWidget(tab_bg)

        # ── Tab 1: Calidad 4x (con botones circulares 1, 2, 3, 4) ────────────
        tab_qual = QWidget()
        t1_layout = QHBoxLayout(tab_qual)
        t1_layout.setContentsMargins(0, 0, 0, 0)
        t1_layout.setSpacing(10)
        t1_layout.addWidget(QLabel(t("lbl_ai_model")))
        self.combo_qual_model = QComboBox()
        self.combo_qual_model.addItems([
            "realesrgan-x4plus (Fotos)",
            "realesrgan-x4plus-anime (Ilustraciones/Anime)"
        ])
        t1_layout.addWidget(self.combo_qual_model)

        t1_layout.addSpacing(8)
        t1_layout.addWidget(QLabel(t("lbl_scale")))

        self.tta_level_group = QButtonGroup(self)
        self.tta_level_group.setExclusive(True)
        self.tta_circle_buttons: dict[int, QPushButton] = {}

        circles_layout = QHBoxLayout()
        circles_layout.setContentsMargins(0, 0, 0, 0)
        circles_layout.setSpacing(6)

        for lvl in (1, 2, 3, 4):
            c_btn = QPushButton(str(lvl))
            c_btn.setObjectName("ttaCircleBtn")
            c_btn.setFixedSize(34, 34)
            c_btn.setCheckable(True)
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setToolTip(f"Nivel de procesamiento TTA / Escala: {lvl}")
            if lvl == 4:
                c_btn.setChecked(True)
            c_btn.clicked.connect(lambda checked, level=lvl: self._on_tta_level_selected(level))
            self.tta_level_group.addButton(c_btn, lvl)
            self.tta_circle_buttons[lvl] = c_btn
            circles_layout.addWidget(c_btn)

        t1_layout.addLayout(circles_layout)
        t1_layout.addSpacing(8)

        self.chk_tta = QCheckBox(t("chk_tta"))
        t1_layout.addWidget(self.chk_tta)
        t1_layout.addStretch()
        self.options_stack.addWidget(tab_qual)

        # ── Tab 2: Marca de Agua Avanzada ────────────────────────────────────
        tab_wm = QWidget()
        t2_main_layout = QVBoxLayout(tab_wm)
        t2_main_layout.setContentsMargins(0, 0, 0, 0)
        t2_main_layout.setSpacing(8)

        # Fila 1: Tipo, Texto + Color (o Logo), Modo de colocación y Opacidad
        t2_row1 = QHBoxLayout()
        t2_row1.setContentsMargins(0, 0, 0, 0)
        t2_row1.setSpacing(8)

        t2_row1.addWidget(QLabel(t("lbl_type")))
        self.combo_wm_type = QComboBox()
        self.combo_wm_type.addItems([t("type_text"), t("type_image")])
        self.combo_wm_type.currentIndexChanged.connect(self._on_wm_type_changed)
        t2_row1.addWidget(self.combo_wm_type)

        # Contenedor de Texto + Selector de Color
        self.wm_text_container = QWidget()
        wt_layout = QHBoxLayout(self.wm_text_container)
        wt_layout.setContentsMargins(0, 0, 0, 0)
        wt_layout.setSpacing(6)
        wt_layout.addWidget(QLabel(t("lbl_text")))
        self.txt_watermark = QLineEdit("Media Hub")
        self.txt_watermark.setFixedWidth(135)
        self.txt_watermark.textChanged.connect(self._update_watermark_live_preview)
        wt_layout.addWidget(self.txt_watermark)

        wt_layout.addWidget(QLabel(t("lbl_color")))
        self.btn_wm_color = QPushButton()
        self.btn_wm_color.setObjectName("colorSwatchBtn")
        self.btn_wm_color.setFixedSize(78, 30)
        self.btn_wm_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wm_color.clicked.connect(self._pick_watermark_color)
        self._refresh_color_button_style()
        wt_layout.addWidget(self.btn_wm_color)
        t2_row1.addWidget(self.wm_text_container)

        # Contenedor de Imagen / Logo
        self.wm_image_container = QWidget()
        wi_layout = QHBoxLayout(self.wm_image_container)
        wi_layout.setContentsMargins(0, 0, 0, 0)
        wi_layout.setSpacing(6)
        self.btn_select_logo = QPushButton(t("btn_select_logo"))
        self.btn_select_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_logo.clicked.connect(self._pick_logo_file)
        self.lbl_logo_name = QLabel(t("no_logo_selected"))
        self.lbl_logo_name.setStyleSheet("color: #9CA3AF; font-size: 8.5pt;")
        wi_layout.addWidget(self.btn_select_logo)
        wi_layout.addWidget(self.lbl_logo_name)
        self.wm_image_container.setVisible(False)
        t2_row1.addWidget(self.wm_image_container)

        t2_row1.addWidget(QLabel(t("lbl_mode")))
        self.combo_wm_mode = QComboBox()
        self.combo_wm_mode.addItem(t("mode_xy"), "xy")
        self.combo_wm_mode.addItem(t("mode_mosaic_diag"), "mosaic_diag")
        self.combo_wm_mode.addItem(t("mode_mosaic_horiz"), "mosaic_horiz")
        self.combo_wm_mode.addItem(t("mode_mosaic_vert"), "mosaic_vert")
        self.combo_wm_mode.currentIndexChanged.connect(self._on_wm_mode_changed)
        t2_row1.addWidget(self.combo_wm_mode)

        t2_row1.addWidget(QLabel(t("lbl_opacity")))
        self.spin_wm_opac = QSpinBox()
        self.spin_wm_opac.setRange(10, 100)
        self.spin_wm_opac.setValue(70)
        self.spin_wm_opac.setSuffix("%")
        self.spin_wm_opac.valueChanged.connect(self._update_watermark_live_preview)
        t2_row1.addWidget(self.spin_wm_opac)

        t2_row1.addStretch()
        t2_main_layout.addLayout(t2_row1)

        # Fila 2: Tamaño, Espaciado de letras, Separación de mosaico, Coordenadas X-Y y Dirección (°)
        t2_row2 = QHBoxLayout()
        t2_row2.setContentsMargins(0, 0, 0, 0)
        t2_row2.setSpacing(8)

        t2_row2.addWidget(QLabel(t("lbl_font_size")))
        self.spin_wm_size = QSpinBox()
        self.spin_wm_size.setRange(10, 220)
        self.spin_wm_size.setValue(40)
        self.spin_wm_size.setSuffix(" px")
        self.spin_wm_size.valueChanged.connect(self._update_watermark_live_preview)
        t2_row2.addWidget(self.spin_wm_size)

        self.lbl_wm_spacing = QLabel(t("lbl_letter_spacing"))
        t2_row2.addWidget(self.lbl_wm_spacing)
        self.spin_wm_spacing = QSpinBox()
        self.spin_wm_spacing.setRange(0, 60)
        self.spin_wm_spacing.setValue(2)
        self.spin_wm_spacing.setSuffix(" px")
        self.spin_wm_spacing.valueChanged.connect(self._update_watermark_live_preview)
        t2_row2.addWidget(self.spin_wm_spacing)

        self.lbl_wm_separation = QLabel(t("lbl_separation"))
        t2_row2.addWidget(self.lbl_wm_separation)
        self.spin_wm_separation = QSpinBox()
        self.spin_wm_separation.setRange(20, 500)
        self.spin_wm_separation.setValue(120)
        self.spin_wm_separation.setSuffix(" px")
        self.spin_wm_separation.setEnabled(False)
        self.spin_wm_separation.valueChanged.connect(self._update_watermark_live_preview)
        t2_row2.addWidget(self.spin_wm_separation)

        self.lbl_wm_x = QLabel(t("lbl_pos_x"))
        t2_row2.addWidget(self.lbl_wm_x)
        self.spin_wm_x = QSpinBox()
        self.spin_wm_x.setRange(0, 100)
        self.spin_wm_x.setValue(50)
        self.spin_wm_x.setSuffix("%")
        self.spin_wm_x.valueChanged.connect(self._update_watermark_live_preview)
        t2_row2.addWidget(self.spin_wm_x)

        self.lbl_wm_y = QLabel(t("lbl_pos_y"))
        t2_row2.addWidget(self.lbl_wm_y)
        self.spin_wm_y = QSpinBox()
        self.spin_wm_y.setRange(0, 100)
        self.spin_wm_y.setValue(50)
        self.spin_wm_y.setSuffix("%")
        self.spin_wm_y.valueChanged.connect(self._update_watermark_live_preview)
        t2_row2.addWidget(self.spin_wm_y)

        t2_row2.addWidget(QLabel(t("lbl_angle")))
        self.spin_wm_angle = QSpinBox()
        self.spin_wm_angle.setRange(-180, 180)
        self.spin_wm_angle.setValue(0)
        self.spin_wm_angle.setSuffix("°")
        self.spin_wm_angle.valueChanged.connect(self._update_watermark_live_preview)
        t2_row2.addWidget(self.spin_wm_angle)

        t2_row2.addStretch()
        t2_main_layout.addLayout(t2_row2)

        self.options_stack.addWidget(tab_wm)

        # ── Tab 3: Comprimir ─────────────────────────────────────────────────
        tab_comp = QWidget()
        t3_layout = QHBoxLayout(tab_comp)
        t3_layout.setContentsMargins(0, 0, 0, 0)
        t3_layout.addWidget(QLabel(t("lbl_format")))
        self.combo_comp_fmt = QComboBox()
        self.combo_comp_fmt.addItems(["webp", "jpg", "png"])
        t3_layout.addWidget(self.combo_comp_fmt)
        t3_layout.addWidget(QLabel(t("lbl_quality")))
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(20, 100)
        self.slider_quality.setValue(80)
        self.lbl_qual_val = QLabel("80%")
        self.slider_quality.valueChanged.connect(lambda v: self.lbl_qual_val.setText(f"{v}%"))
        t3_layout.addWidget(self.slider_quality)
        t3_layout.addWidget(self.lbl_qual_val)
        t3_layout.addStretch()
        self.options_stack.addWidget(tab_comp)

        c_layout.addWidget(self.options_stack)

        # ── Barra inferior de acción (Procesar Imagen + Guardar Copia) ───────
        bottom_box = QHBoxLayout()
        bottom_box.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        bottom_box.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        bottom_box.addWidget(self.status_label, stretch=1)

        self.btn_process = QPushButton(t("btn_process"))
        self.btn_process.setObjectName("btnProcess")
        self.btn_process.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_process.clicked.connect(self._start_process)
        bottom_box.addWidget(self.btn_process)

        self.btn_save = QPushButton(t("btn_save"))
        self.btn_save.setObjectName("btnSave")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_processed_image)
        bottom_box.addWidget(self.btn_save)

        c_layout.addLayout(bottom_box)
        main_layout.addWidget(content_frame, stretch=1)

        # Activar primera pestaña
        self._switch_tab(0)

    def _on_tta_level_selected(self, level: int):
        self.selected_tta_level = level
        SoundManager.instance().play("click")

    def _refresh_color_button_style(self):
        c = QColor(self.wm_text_color)
        lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
        text_col = "#111827" if lum > 150 else "#F9FAFB"
        self.btn_wm_color.setText(self.wm_text_color.upper())
        self.btn_wm_color.setStyleSheet(
            f"background-color: {self.wm_text_color}; color: {text_col}; "
            f"border: 1px solid #3B4258; border-radius: 6px; font-weight: 700; font-size: 8.5pt;"
        )

    def _pick_watermark_color(self):
        initial = QColor(self.wm_text_color)
        chosen = QColorDialog.getColor(initial, self, t("lbl_color"))
        if chosen.isValid():
            self.wm_text_color = chosen.name().upper()
            self._refresh_color_button_style()
            self._update_watermark_live_preview()

    def _on_wm_type_changed(self, idx: int):
        is_text = (idx == 0)
        self.wm_text_container.setVisible(is_text)
        self.wm_image_container.setVisible(not is_text)
        self.spin_wm_spacing.setEnabled(is_text)
        self._update_watermark_live_preview()

    def _on_wm_mode_changed(self, idx: int):
        mode = self.combo_wm_mode.currentData() or "xy"
        is_xy = (mode == "xy")
        self.spin_wm_x.setEnabled(is_xy)
        self.spin_wm_y.setEnabled(is_xy)
        self.spin_wm_separation.setEnabled(not is_xy)
        self._update_watermark_live_preview()

    def _pick_logo_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, t("dialog_select_logo_title"), "",
            "Imágenes PNG/JPG (*.png *.jpg *.jpeg *.webp)"
        )
        if file:
            self.current_logo_path = file
            self.lbl_logo_name.setText(os.path.basename(file))
            self._update_watermark_live_preview()

    def _get_watermark_params(self) -> dict:
        wm_type = "texto" if self.combo_wm_type.currentIndex() == 0 else "imagen"
        return {
            "wm_type": wm_type,
            "text": self.txt_watermark.text().strip() or "Media Hub",
            "logo": self.current_logo_path,
            "color": self.wm_text_color,
            "mode": self.combo_wm_mode.currentData() or "xy",
            "opacity": self.spin_wm_opac.value(),
            "font_size": self.spin_wm_size.value(),
            "letter_spacing": self.spin_wm_spacing.value(),
            "separation": self.spin_wm_separation.value(),
            "pos_x": self.spin_wm_x.value(),
            "pos_y": self.spin_wm_y.value(),
            "angle": self.spin_wm_angle.value(),
        }

    def _ensure_preview_pil_cache(self):
        if self._preview_pil_cache is not None:
            return
        if not self.current_orig_path or not os.path.exists(self.current_orig_path):
            return
        try:
            img = Image.open(self.current_orig_path).convert("RGBA")
            max_dim = 1100
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            self._preview_pil_cache = img
        except Exception:
            self._preview_pil_cache = None

    def _update_watermark_live_preview(self):
        """Genera una vista previa instantánea en vivo del resultado en el split slider."""
        if self.options_stack.currentIndex() != 2:
            return
        if not self.current_orig_path or not os.path.exists(self.current_orig_path):
            return

        self._ensure_preview_pil_cache()
        if self._preview_pil_cache is None:
            return

        wm_params = self._get_watermark_params()
        if wm_params["wm_type"] == "imagen" and (not wm_params["logo"] or not os.path.exists(wm_params["logo"])):
            return

        rendered_pil = WatermarkLogic.render_watermark_pil(self._preview_pil_cache, wm_params)
        preview_px = pil_to_qpixmap(rendered_pil)
        self.split_preview.set_after_pixmap(preview_px)
        self.btn_save.setEnabled(True)

    def _switch_tab(self, index: int):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.options_stack.setCurrentIndex(index)
        if index == 2 and self.current_orig_path:
            self._update_watermark_live_preview()

    def _pick_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, t("dialog_select_img_title"), "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)"
        )
        if file:
            self.current_orig_path = file
            self.current_dest_path = None
            self._preview_pil_cache = None
            self.btn_save.setEnabled(False)
            self.file_label.setText(os.path.basename(file))
            self.split_preview.set_images(file, None)
            self.status_label.setText(t("status_ready"))
            if self.options_stack.currentIndex() == 2:
                self._update_watermark_live_preview()

    def _get_output_dir(self):
        if self.last_saved_dir and os.path.isdir(self.last_saved_dir):
            return self.last_saved_dir
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        dest = os.path.join(home, "Downloads", "MediaHub_Images")
        os.makedirs(dest, exist_ok=True)
        return dest

    def _open_output_dir(self):
        d = self._get_output_dir()
        try:
            os.startfile(d)
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"No se pudo abrir la carpeta:\n{e}")

    def _build_suggested_copy_filename(self, idx: int) -> tuple[str, str]:
        base_name, _ = os.path.splitext(os.path.basename(self.current_orig_path or "imagen"))
        if idx == 0:
            return f"{base_name}_copia_nobg.png", "PNG (*.png)"
        elif idx == 1:
            return f"{base_name}_copia_{self.selected_tta_level}x.png", "PNG (*.png)"
        elif idx == 2:
            return f"{base_name}_copia_watermark.png", "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)"
        else:
            fmt = self.combo_comp_fmt.currentText().lower()
            return f"{base_name}_copia_optimized.{fmt}", f"{fmt.upper()} (*.{fmt})"

    def _start_process(self):
        if not self.current_orig_path or not os.path.isfile(self.current_orig_path):
            QMessageBox.warning(self, t("dialog_attention"), t("msg_select_first"))
            return

        idx = self.options_stack.currentIndex()
        os.makedirs(self._staging_dir, exist_ok=True)
        base_name, _ = os.path.splitext(os.path.basename(self.current_orig_path))

        params = {"orig": self.current_orig_path}

        if idx == 0:
            task_type = "bg_remover"
            dest = os.path.join(self._staging_dir, f"{base_name}_staged_nobg.png")
            m_text = self.combo_bg_model.currentText().split()[0]
            params.update({"dest": dest, "model": m_text, "alpha": self.chk_alpha.isChecked()})

        elif idx == 1:
            task_type = "quality"
            scale = self.selected_tta_level
            dest = os.path.join(self._staging_dir, f"{base_name}_staged_{scale}x.png")
            m_text = self.combo_qual_model.currentText().split()[0]
            params.update({
                "dest": dest,
                "model": m_text,
                "scale": scale,
                "tta": self.chk_tta.isChecked()
            })

        elif idx == 2:
            task_type = "watermark"
            dest = os.path.join(self._staging_dir, f"{base_name}_staged_watermark.png")
            wm_params = self._get_watermark_params()
            if wm_params["wm_type"] == "imagen" and (not wm_params["logo"] or not os.path.exists(wm_params["logo"])):
                QMessageBox.warning(self, t("dialog_attention"), t("msg_select_logo_first"))
                return
            params.update(wm_params)
            params["dest"] = dest

        else:
            task_type = "compress"
            fmt = self.combo_comp_fmt.currentText().lower()
            dest = os.path.join(self._staging_dir, f"{base_name}_staged_optimized.{fmt}")
            params.update({"dest": dest, "fmt": fmt, "quality": self.slider_quality.value()})

        self.btn_process.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(15)
        self.status_label.setText(t("status_processing"))

        self.current_worker = ImageWorker(task_type, params, self)
        self.current_worker.progress.connect(self._on_worker_progress)
        self.current_worker.finished.connect(self._on_worker_finished)
        self.current_worker.error.connect(self._on_worker_error)
        self.current_worker.start()

    def _on_worker_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_label.setText(msg)

    def _on_worker_finished(self, msg: str, saved_path: str):
        SoundManager.instance().play("success")
        self.btn_process.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.current_dest_path = saved_path
        self.status_label.setText(t("status_done"))
        self.split_preview.set_images(self.current_orig_path, saved_path)

    def _on_worker_error(self, err: str):
        self.btn_process.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(t("status_error"))
        QMessageBox.critical(self, t("dialog_error"), err)

    def _save_processed_image(self):
        """Guarda una copia de la imagen procesada sin sobrescribir jamás la imagen original."""
        if not self.current_orig_path or not os.path.isfile(self.current_orig_path):
            QMessageBox.warning(self, t("dialog_attention"), t("msg_select_first"))
            return

        idx = self.options_stack.currentIndex()

        # Si estamos en Marca de Agua, renderizar en alta resolución al momento de guardar
        # para garantizar que refleje exactamente los controles actuales del live preview
        if idx == 2:
            wm_params = self._get_watermark_params()
            if wm_params["wm_type"] == "imagen" and (not wm_params["logo"] or not os.path.exists(wm_params["logo"])):
                QMessageBox.warning(self, t("dialog_attention"), t("msg_select_logo_first"))
                return
            try:
                base_name, _ = os.path.splitext(os.path.basename(self.current_orig_path))
                staged_wm = os.path.join(self._staging_dir, f"{base_name}_staged_watermark.png")
                base_img = Image.open(self.current_orig_path).convert("RGBA")
                res_img = WatermarkLogic.render_watermark_pil(base_img, wm_params)
                res_img.save(staged_wm)
                self.current_dest_path = staged_wm
            except Exception as e:
                QMessageBox.critical(self, t("dialog_error"), str(e))
                return

        if not self.current_dest_path or not os.path.isfile(self.current_dest_path):
            QMessageBox.warning(self, t("dialog_attention"), t("msg_process_before_save"))
            return

        suggested_name, file_filter = self._build_suggested_copy_filename(idx)
        initial_dir = self._get_output_dir()
        default_target = os.path.join(initial_dir, suggested_name)

        target_path, _ = QFileDialog.getSaveFileName(
            self,
            t("dialog_save_title"),
            default_target,
            file_filter
        )
        if not target_path:
            return

        # Garantizar que nunca sobrescriba el archivo original seleccionado
        orig_norm = os.path.normcase(os.path.abspath(self.current_orig_path))
        target_norm = os.path.normcase(os.path.abspath(target_path))
        if target_norm == orig_norm:
            root_p, ext_p = os.path.splitext(target_path)
            target_path = f"{root_p}_copia{ext_p or '.png'}"

        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            target_ext = os.path.splitext(target_path)[1].lower()
            src_ext = os.path.splitext(self.current_dest_path)[1].lower()

            if target_ext and target_ext != src_ext:
                img = Image.open(self.current_dest_path)
                ImageFormats._save_image(img, target_path, target_ext.lstrip("."))
            else:
                shutil.copy2(self.current_dest_path, target_path)

            self.last_saved_dir = os.path.dirname(os.path.abspath(target_path))
            SoundManager.instance().play("success")
            self.status_label.setText(t("status_saved", name=os.path.basename(target_path)))
            QMessageBox.information(
                self,
                t("dialog_saved_title"),
                t("msg_saved_success", path=target_path)
            )
        except Exception as e:
            QMessageBox.critical(self, t("dialog_error"), str(e))

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F1117;
                color: #F3F4F6;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QFrame#sidebar {
                background-color: #161822;
                border-right: 1px solid #232736;
            }
            QLabel#sidebarTitle {
                color: #FFFFFF;
                font-size: 14pt;
                font-weight: 800;
                letter-spacing: -0.3px;
            }
            QLabel#sidebarSubtitle {
                color: #828B9E;
                font-size: 9pt;
            }
            QPushButton#navBtn {
                background-color: transparent;
                color: #9CA3AF;
                border: none;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 10pt;
                font-weight: 600;
                text-align: left;
            }
            QPushButton#navBtn:hover {
                background-color: #1F2332;
                color: #FFFFFF;
            }
            QPushButton#navBtn:checked {
                background-color: #2563EB;
                color: #FFFFFF;
            }
            QPushButton#navSecondaryBtn {
                background-color: #1E2230;
                color: #D1D5DB;
                border: 1px solid #2B3144;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton#navSecondaryBtn:hover {
                background-color: #272C3E;
                color: #FFFFFF;
            }
            QFrame#contentFrame {
                background-color: #0F1117;
            }
            QFrame#fileBox {
                background-color: #161822;
                border: 1px solid #232736;
                border-radius: 12px;
            }
            QLabel#fileLabel {
                color: #9CA3AF;
                font-size: 9.5pt;
                font-weight: 500;
            }
            QPushButton#actionBtnPrimary {
                background-color: #1F2433;
                color: #FFFFFF;
                border: 1px solid #323A52;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 9.5pt;
                font-weight: 600;
            }
            QPushButton#actionBtnPrimary:hover {
                background-color: #2B334A;
            }
            QPushButton#ttaCircleBtn {
                background-color: #161822;
                color: #9CA3AF;
                border: 1.5px solid #2B3144;
                border-radius: 17px;
                font-size: 9.5pt;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton#ttaCircleBtn:hover {
                background-color: #1F2437;
                color: #FFFFFF;
                border-color: #3B82F6;
            }
            QPushButton#ttaCircleBtn:checked {
                background-color: #2563EB;
                color: #FFFFFF;
                border: 1.5px solid #60A5FA;
            }
            QPushButton#btnProcess {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 10px 22px;
                font-size: 10.5pt;
                font-weight: 700;
            }
            QPushButton#btnProcess:hover {
                background-color: #1D4ED8;
            }
            QPushButton#btnProcess:disabled {
                background-color: #1E2333;
                color: #6B7280;
            }
            QPushButton#btnSave {
                background-color: #10B981;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 10px 22px;
                font-size: 10.5pt;
                font-weight: 700;
            }
            QPushButton#btnSave:hover {
                background-color: #059669;
            }
            QPushButton#btnSave:disabled {
                background-color: #1A232E;
                color: #4B5563;
            }
            QComboBox, QSpinBox, QLineEdit {
                background-color: #161822;
                color: #F3F4F6;
                border: 1px solid #2B3144;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 9pt;
            }
            QSpinBox:disabled {
                background-color: #12141C;
                color: #4B5563;
                border-color: #1E2230;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #1A1D28;
                color: #F3F4F6;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
                border: 1px solid #2B3144;
                outline: none;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                color: #F3F4F6;
                padding: 4px 8px;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }
            QCheckBox {
                color: #D1D5DB;
                font-size: 9pt;
                font-weight: 500;
            }
            QLabel#statusLabel {
                color: #9CA3AF;
                font-size: 9pt;
                font-weight: 500;
            }
            QProgressBar {
                background-color: #161822;
                border: 1px solid #232736;
                border-radius: 6px;
                min-height: 8px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 6px;
            }
        """)
