from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QStatusBar, QComboBox, QPushButton, QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.database import SessionLocal
from core.models.empresa import Empresa, Sede


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.empresa_activa_id = None
        self.sede_activa_id    = None
        self._session          = SessionLocal()
        self._setup_ui()
        self._cargar_empresas_combo()

    def _setup_ui(self):
        self.setWindowTitle("Sistema Contable")
        self.setMinimumSize(1280, 720)

        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(u"background:  rgb(255, 255, 255);\n"
                              "color: rgb(0, 0, 0);")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_topbar())

        content = QHBoxLayout()
        content.setSpacing(0)
        content.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_bienvenida())
        content.addWidget(self.stack, stretch=1)
        layout.addLayout(content)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo")

    def _build_topbar(self):
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background:#1e293b;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("📊 Sistema Contable")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#f1f5f9;")
        layout.addWidget(title)
        layout.addStretch()

        lbl_emp = QLabel("Empresa:")
        lbl_emp.setStyleSheet("color: rgb(255, 255, 255); font-size:12px;")
        self.combo_empresa = QComboBox()
        self.combo_empresa.setStyleSheet("color: rgb(255, 255, 255);")
        self.combo_empresa.setFixedWidth(220)
        self.combo_empresa.currentIndexChanged.connect(self._on_empresa_changed)

        lbl_sede = QLabel("Sede:")
        lbl_sede.setStyleSheet("color: rgb( 255, 255, 255); font-size:12px; margin-left:12px;")
        self.combo_sede = QComboBox()
        self.combo_sede.setStyleSheet("color: rgb(255, 255, 255);")
        self.combo_sede.setFixedWidth(170)
        self.combo_sede.setEnabled(False)
        self.combo_sede.currentIndexChanged.connect(self._on_sede_changed)

        layout.addWidget(lbl_emp)
        layout.addWidget(self.combo_empresa)
        layout.addWidget(lbl_sede)
        layout.addWidget(self.combo_sede)
        return bar

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background:#0f172a;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(2)

        self._modulos = [
            ("🏢", "Empresas / Sedes",  self._abrir_empresas),
            ("👥", "Terceros",           self._abrir_terceros),
            ("📒", "Contabilidad",       self._abrir_contabilidad),
            ("🧾", "Facturación",        self._abrir_facturacion),
            ("💰", "Tesorería",          self._abrir_tesoreria),
            ("👷", "Nómina",             self._abrir_nomina),
            ("🛡️", "Seguridad Social",   self._abrir_seguridad_social),
            ("📋", "Impuestos",          self._pronto),
            ("📊", "Reportes",           self._pronto),
            ("⚙️", "Configuración",      self._pronto),
        ]

        self._btns_sidebar = []
        for icon, nombre, handler in self._modulos:
            btn = QPushButton(f"  {icon}  {nombre}")
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #cbd5e1;
                    border: none; text-align: left;
                    padding-left: 16px; font-size: 15px;
                }
                QPushButton:hover  { background: #1e293b; color: #f1f5f9; }
                QPushButton:checked { background: #2563eb; color: white; }
            """)
            btn.clicked.connect(lambda checked, h=handler, b=btn: self._nav(h, b))
            layout.addWidget(btn)
            self._btns_sidebar.append(btn)

        layout.addStretch()
        return sidebar

    def _nav(self, handler, btn_activo):
        for btn in self._btns_sidebar:
            btn.setChecked(False)
        btn_activo.setChecked(True)
        handler()

    def _build_bienvenida(self):
        w = QWidget()
        w.setStyleSheet("background:#f8fafc;")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Selecciona un módulo del menú lateral")
        lbl.setFont(QFont("Segoe UI", 14))
        lbl.setStyleSheet("color:#94a3b8;")
        lay.addWidget(lbl)
        return w

    # ── Módulos ────────────────────────────────────────────────

    def _abrir_empresas(self):
        if not hasattr(self, "_widget_empresas"):
            from modules.empresa.widget import EmpresasWidget
            self._widget_empresas = EmpresasWidget()
            self.stack.addWidget(self._widget_empresas)
        self.stack.setCurrentWidget(self._widget_empresas)
        self._cargar_empresas_combo()
        self.status.showMessage("Módulo: Empresas y Sedes")

    def _abrir_terceros(self):
        empresa_id = self.empresa_activa_id
        if not empresa_id:
            QMessageBox.information(self, "Sin empresa",
                                    "Selecciona una empresa en la barra superior.")
            return
        clave = f"_widget_terceros_{empresa_id}"
        if not hasattr(self, clave):
            from modules.terceros.widget import TercerosWidget
            widget = TercerosWidget(empresa_id)
            self.stack.addWidget(widget)
            setattr(self, clave, widget)
        self.stack.setCurrentWidget(getattr(self, clave))
        self.status.showMessage("Módulo: Terceros")

    def _abrir_contabilidad(self):
        # Siempre recrea si cambió la empresa
        empresa_id = self.empresa_activa_id
        clave = f"_widget_contabilidad_{empresa_id}"
        if not hasattr(self, clave):
            from modules.contabilidad.widget import ContabilidadWidget
            widget = ContabilidadWidget(empresa_id)
            self.stack.addWidget(widget)
            setattr(self, clave, widget)
        self.stack.setCurrentWidget(getattr(self, clave))
        self.status.showMessage("Módulo: Contabilidad")

    def _abrir_seguridad_social(self):
        empresa_id = self.empresa_activa_id
        if not empresa_id:
            QMessageBox.information(self, "Sin empresa",
                                    "Selecciona una empresa en la barra superior.")
            return
        clave = f"_widget_ss_{empresa_id}"
        if not hasattr(self, clave):
            from modules.seguridad_social.widget import SeguridadSocialWidget
            widget = SeguridadSocialWidget(empresa_id)
            self.stack.addWidget(widget)
            setattr(self, clave, widget)
        self.stack.setCurrentWidget(getattr(self, clave))
        self.status.showMessage("Módulo: Seguridad Social")

    def _abrir_tesoreria(self):
        empresa_id = self.empresa_activa_id
        if not empresa_id:
            QMessageBox.information(self, "Sin empresa",
                                    "Selecciona una empresa en la barra superior.")
            return
        clave = f"_widget_tesoreria_{empresa_id}"
        if not hasattr(self, clave):
            from core.database import engine, Base
            from core.models import tesoreria  # noqa
            Base.metadata.create_all(bind=engine)
            from modules.tesoreria.widget import TesoreriaWidget
            widget = TesoreriaWidget(empresa_id)
            self.stack.addWidget(widget)
            setattr(self, clave, widget)
        self.stack.setCurrentWidget(getattr(self, clave))
        self.status.showMessage("Módulo: Tesorería")

    def _abrir_facturacion(self):
        empresa_id = self.empresa_activa_id
        if not empresa_id:
            QMessageBox.information(self, "Sin empresa",
                                    "Selecciona una empresa en la barra superior.")
            return
        clave = f"_widget_facturacion_{empresa_id}"
        if not hasattr(self, clave):
            from modules.facturacion.widget import FacturacionWidget
            widget = FacturacionWidget(empresa_id)
            self.stack.addWidget(widget)
            setattr(self, clave, widget)
        self.stack.setCurrentWidget(getattr(self, clave))
        self.status.showMessage("Módulo: Facturación")

    def _abrir_nomina(self):
        empresa_id = self.empresa_activa_id
        if not empresa_id:
            QMessageBox.information(self, "Sin empresa",
                                    "Selecciona una empresa en la barra superior.")
            return
        clave = f"_widget_nomina_{empresa_id}"
        if not hasattr(self, clave):
            from modules.nomina.widget import NominaWidget
            widget = NominaWidget(empresa_id)
            self.stack.addWidget(widget)
            setattr(self, clave, widget)
        self.stack.setCurrentWidget(getattr(self, clave))
        self.status.showMessage("Módulo: Nómina")

    def _pronto(self):
        if not hasattr(self, "_widget_pronto"):
            w = QWidget()
            w.setStyleSheet("background:#f8fafc;")
            lay = QVBoxLayout(w)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel("🚧  Módulo en desarrollo")
            lbl.setFont(QFont("Segoe UI", 16))
            lbl.setStyleSheet("color:#94a3b8;")
            lay.addWidget(lbl)
            self._widget_pronto = w
            self.stack.addWidget(w)
        self.stack.setCurrentWidget(self._widget_pronto)

    # ── Combos ─────────────────────────────────────────────────

    def _cargar_empresas_combo(self):
        self.combo_empresa.blockSignals(True)
        anterior = self.empresa_activa_id
        self.combo_empresa.clear()
        self.combo_empresa.addItem("— Seleccionar —", None)
        empresas = (
            self._session.query(Empresa)
            .filter_by(activa=True)
            .order_by(Empresa.razon_social)
            .all()
        )
        idx_restaurar = 0
        for i, emp in enumerate(empresas, 1):
            self.combo_empresa.addItem(emp.razon_social, emp.id)
            if emp.id == anterior:
                idx_restaurar = i
        self.combo_empresa.setCurrentIndex(idx_restaurar)
        self.combo_empresa.blockSignals(False)

    def _on_empresa_changed(self, index):
        empresa_id = self.combo_empresa.itemData(index)
        self.empresa_activa_id = empresa_id
        self.combo_sede.clear()
        self.combo_sede.setEnabled(empresa_id is not None)
        if empresa_id:
            sedes = (
                self._session.query(Sede)
                .filter_by(empresa_id=empresa_id, activa=True)
                .all()
            )
            for sede in sedes:
                self.combo_sede.addItem(sede.nombre, sede.id)
            self.status.showMessage(
                f"Empresa activa: {self.combo_empresa.currentText()}"
            )

    def _on_sede_changed(self, index):
        self.sede_activa_id = self.combo_sede.itemData(index)

    def closeEvent(self, event):
        self._session.close()
        super().closeEvent(event)
