from decimal import Decimal, InvalidOperation
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QTabWidget, QComboBox, QDateEdit,
    QFrame, QSplitter, QSpinBox, QFormLayout, QCheckBox,
    QListWidget, QListWidgetItem, QTextBrowser, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from core.models.contabilidad import (
    EstadoPeriodo, EstadoAsiento,
    NaturalezaCuenta, ClaseCuenta, TipoCuenta,
    NivelCuenta, ModuloCuenta
)
from modules.contabilidad.service import ContabilidadService

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

COLOR_CLASE = {
    "1": "#dbeafe", "2": "#fee2e2", "3": "#dcfce7",
    "4": "#d1fae5", "5": "#fef9c3", "6": "#ffe4e6",
    "7": "#f3e8ff", "8": "#e0f2fe", "9": "#fce7f3",
}

# Mapeo clase → tipos disponibles
TIPOS_POR_CLASE = {
    ClaseCuenta.ACTIVO: [
        TipoCuenta.ACTIVO_CORRIENTE,
        TipoCuenta.ACTIVO_NO_CORRIENTE,
    ],
    ClaseCuenta.PASIVO: [
        TipoCuenta.PASIVO_CORRIENTE,
        TipoCuenta.PASIVO_NO_CORRIENTE,
    ],
    ClaseCuenta.PATRIMONIO: [
        TipoCuenta.CAPITAL,
        TipoCuenta.RESERVAS,
        TipoCuenta.RESULTADOS,
    ],
    ClaseCuenta.INGRESO: [
        TipoCuenta.INGRESO_OPERACIONAL,
        TipoCuenta.INGRESO_NO_OPERACIONAL,
    ],
    ClaseCuenta.GASTO: [
        TipoCuenta.GASTO_OPERACIONAL,
        TipoCuenta.GASTO_NO_OPERACIONAL,
    ],
    ClaseCuenta.COSTO_DE_VENTA: [TipoCuenta.COSTO_VENTA],
    ClaseCuenta.COSTO_DE_PRODUCCION: [TipoCuenta.COSTO_PRODUCCION],
    ClaseCuenta.CUENTAS_DE_ORDEN_DEUDORAS: [TipoCuenta.ORDEN_DEUDORA],
    ClaseCuenta.CUENTAS_DE_ORDEN_ACREEDORAS: [TipoCuenta.ORDEN_ACREEDORA],
}

BTN_PRIMARY = (
    "background:#2563eb; color:white; padding:5px 16px; "
    "border-radius:5px; font-weight:bold;"
)
BTN_SUCCESS = (
    "background:#059669; color:white; padding:5px 16px; "
    "border-radius:5px; font-weight:bold;"
)


# ══════════════════════════════════════════════════════════════
# Diálogo: Nueva Cuenta PUC
# ══════════════════════════════════════════════════════════════
class DialogNuevaCuenta(QDialog):
    def __init__(self, service: ContabilidadService, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Nueva cuenta contable")
        self.setMinimumSize(860, 660)
        self._build_ui()

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ─── Panel izquierdo: formulario ───────────────────────
        left_widget = QWidget()
        left_widget.setStyleSheet("background:#f8fafc;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(12)

        titulo = QLabel("📋  Nueva cuenta contable")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b;")
        left_layout.addWidget(titulo)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        # Código
        self.f_codigo = QLineEdit()
        self.f_codigo.setPlaceholderText("Ej: 110505")
        self.f_codigo.setMaxLength(20)
        self.f_codigo.textChanged.connect(self._on_codigo_changed)

        # Nombre
        self.f_nombre = QLineEdit()
        self.f_nombre.setPlaceholderText("Nombre de la cuenta")

        # Nivel (no permite clase)
        self.cb_nivel = QComboBox()
        for n in NivelCuenta:
            self.cb_nivel.addItem(n.value.capitalize(), n)
        self.cb_nivel.currentIndexChanged.connect(self._actualizar_acepta_mov)

        # Naturaleza
        self.cb_naturaleza = QComboBox()
        self.cb_naturaleza.addItem("Débito", NaturalezaCuenta.DEBITO)
        self.cb_naturaleza.addItem("Crédito", NaturalezaCuenta.CREDITO)

        # Clase
        self.cb_clase = QComboBox()
        self.cb_clase.addItem("— Seleccione —", None)
        for c in ClaseCuenta:
            self.cb_clase.addItem(c.value.capitalize(), c)
        self.cb_clase.currentIndexChanged.connect(self._on_clase_changed)

        # Tipo (depende de clase)
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItem("— Seleccione —", None)

        # Módulo
        self.cb_modulo = QComboBox()
        for m in ModuloCuenta:
            label = {
                "efectivo": "💵 Efectivo (Caja/Bancos)",
                "cuentas por cobrar": "📥 Cuentas por Cobrar",
                "cuentas por pagar": "📤 Cuentas por Pagar",
                "diferida": "⏳ Diferida",
                "inventario": "📦 Inventario",
                "nomina": "👷 Nómina",
                "activo fijo": "🏗️ Activo Fijo",
                "general": "🔹 General",
            }.get(m.value, m.value.capitalize())
            self.cb_modulo.addItem(label, m)

        # Retención / Impuesto
        retencion_row = QHBoxLayout()
        self.chk_retencion = QCheckBox("Es retención")
        self.chk_impuesto  = QCheckBox("Es impuesto")
        self.chk_retencion.toggled.connect(self._on_fiscal_changed)
        self.chk_impuesto.toggled.connect(self._on_fiscal_changed)
        retencion_row.addWidget(self.chk_retencion)
        retencion_row.addWidget(self.chk_impuesto)
        retencion_row.addStretch()

        # Tarifa
        tarifa_row = QHBoxLayout()
        self.spin_tarifa = QDoubleSpinBox()
        self.spin_tarifa.setRange(0, 100)
        self.spin_tarifa.setDecimals(4)
        self.spin_tarifa.setSuffix(" %")
        self.spin_tarifa.setFixedWidth(120)
        self.spin_tarifa.setEnabled(False)
        self.lbl_tarifa = QLabel("Tarifa:")
        self.lbl_tarifa.setEnabled(False)
        tarifa_row.addWidget(self.lbl_tarifa)
        tarifa_row.addWidget(self.spin_tarifa)
        tarifa_row.addStretch()

        # Acepta movimientos (auto)
        self.lbl_acepta = QLabel("✅ Esta cuenta acepta movimientos directos")
        self.lbl_acepta.setStyleSheet("color:#16a34a; font-size:11px;")

        # Cuenta padre
        self.f_padre = QLineEdit()
        self.f_padre.setPlaceholderText("Código de la cuenta padre (opcional)")

        form.addRow("Código *:", self.f_codigo)
        form.addRow("Nombre *:", self.f_nombre)
        form.addRow("Nivel *:", self.cb_nivel)
        form.addRow("Naturaleza *:", self.cb_naturaleza)
        form.addRow("Clase *:", self.cb_clase)
        form.addRow("Tipo *:", self.cb_tipo)
        form.addRow("Módulo:", self.cb_modulo)
        form.addRow("Fiscal:", retencion_row)
        form.addRow("", tarifa_row)
        form.addRow("Cuenta padre:", self.f_padre)
        form.addRow("", self.lbl_acepta)

        left_layout.addLayout(form)
        left_layout.addStretch()

        # Botones
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("💾 Crear cuenta")
        self.btn_ok.setFixedWidth(150)
        self.btn_ok.setStyleSheet(BTN_PRIMARY)
        self.btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_ok)
        left_layout.addLayout(btns)

        # ─── Panel derecho: descripción y dinámica ─────────────
        right_widget = QWidget()
        right_widget.setStyleSheet("background:#ffffff; border-left:1px solid #e2e8f0;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(16, 20, 16, 16)
        right_layout.setSpacing(8)

        lbl_info = QLabel("📖  Información PUC")
        lbl_info.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_info.setStyleSheet("color:#374151;")
        right_layout.addWidget(lbl_info)

        self.lbl_codigo_ref = QLabel("Escribe el código para ver la información")
        self.lbl_codigo_ref.setStyleSheet("color:#94a3b8; font-size:11px;")
        right_layout.addWidget(self.lbl_codigo_ref)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        right_layout.addWidget(sep)

        self.txt_contenido = QTextBrowser()
        self.txt_contenido.setOpenExternalLinks(False)
        self.txt_contenido.setStyleSheet(
            "background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; "
            "font-size:12px; font-family:'Segoe UI', sans-serif; padding:8px;"
        )
        self.txt_contenido.setPlaceholderText(
            "Aquí aparecerá la descripción y dinámica de la cuenta según el PUC colombiano."
        )
        right_layout.addWidget(self.txt_contenido, stretch=1)

        main.addWidget(left_widget, stretch=1)
        main.addWidget(right_widget, stretch=1)

        # Timer para búsqueda diferida
        self._timer_puc = QTimer()
        self._timer_puc.setSingleShot(True)
        self._timer_puc.setInterval(400)
        self._timer_puc.timeout.connect(self._buscar_info_puc)

    def _on_codigo_changed(self, text: str):
        self._timer_puc.start()

    def _buscar_info_puc(self):
        codigo = self.f_codigo.text().strip()
        if len(codigo) < 2:
            self.txt_contenido.clear()
            self.lbl_codigo_ref.setText("Escribe el código para ver la información")
            return

        contenido = self.service.obtener_contenido_puc(codigo)
        if contenido:
            self.lbl_codigo_ref.setText(f"Cuenta: {codigo}")
            self.lbl_codigo_ref.setStyleSheet("color:#2563eb; font-size:11px; font-weight:bold;")
            self.txt_contenido.setHtml(contenido.contenido)
        else:
            self.lbl_codigo_ref.setText(f"Sin información PUC para: {codigo}")
            self.lbl_codigo_ref.setStyleSheet("color:#94a3b8; font-size:11px;")
            self.txt_contenido.setHtml(
                "<p style='color:#94a3b8; font-style:italic;'>"
                "No hay descripción registrada para este código.</p>"
            )

    def _on_clase_changed(self):
        clase = self.cb_clase.currentData()
        self.cb_tipo.clear()
        self.cb_tipo.addItem("— Seleccione —", None)
        if clase and clase in TIPOS_POR_CLASE:
            for t in TIPOS_POR_CLASE[clase]:
                self.cb_tipo.addItem(t.value.replace("_", " ").capitalize(), t)

    def _on_fiscal_changed(self):
        es_fiscal = self.chk_retencion.isChecked() or self.chk_impuesto.isChecked()
        self.spin_tarifa.setEnabled(es_fiscal)
        self.lbl_tarifa.setEnabled(es_fiscal)
        if not es_fiscal:
            self.spin_tarifa.setValue(0)

    def _actualizar_acepta_mov(self):
        nivel = self.cb_nivel.currentData()
        acepta = nivel in (NivelCuenta.SUBCUENTA, NivelCuenta.AUXILIAR)
        if acepta:
            self.lbl_acepta.setText("✅ Esta cuenta acepta movimientos directos")
            self.lbl_acepta.setStyleSheet("color:#16a34a; font-size:11px;")
        else:
            self.lbl_acepta.setText("⚠️  Esta cuenta es de grupo/mayor (no acepta movimientos directos)")
            self.lbl_acepta.setStyleSheet("color:#d97706; font-size:11px;")

    def _guardar(self):
        codigo = self.f_codigo.text().strip()
        nombre = self.f_nombre.text().strip()

        if not codigo:
            QMessageBox.warning(self, "Campo requerido", "El código es obligatorio.")
            return
        if not nombre:
            QMessageBox.warning(self, "Campo requerido", "El nombre es obligatorio.")
            return
        if self.cb_clase.currentData() is None:
            QMessageBox.warning(self, "Campo requerido", "Selecciona la clase de la cuenta.")
            return
        if self.cb_tipo.currentData() is None:
            QMessageBox.warning(self, "Campo requerido", "Selecciona el tipo de la cuenta.")
            return

        nivel = self.cb_nivel.currentData()
        nivel_num = {
            NivelCuenta.GRUPO: 2,
            NivelCuenta.CUENTA: 3,
            NivelCuenta.SUBCUENTA: 4,
            NivelCuenta.AUXILIAR: 5,
        }.get(nivel, 4)

        acepta_mov = nivel in (NivelCuenta.SUBCUENTA, NivelCuenta.AUXILIAR)

        datos = {
            "codigo":       codigo,
            "nombre":       nombre,
            "naturaleza":   self.cb_naturaleza.currentData(),
            "clase":        self.cb_clase.currentData(),
            "tipo":         self.cb_tipo.currentData(),
            "nivel_nombre": nivel,
            "nivel":        nivel_num,
            "cuenta_padre": self.f_padre.text().strip() or None,
            "acepta_mov":   acepta_mov,
            "es_retencion": self.chk_retencion.isChecked(),
            "es_impuesto":  self.chk_impuesto.isChecked(),
            "tarifa_pct":   self.spin_tarifa.value() if (self.chk_retencion.isChecked() or self.chk_impuesto.isChecked()) else None,
            "modulo":       self.cb_modulo.currentData(),
        }

        try:
            cuenta = self.service.crear_cuenta(datos)
            QMessageBox.information(
                self, "Cuenta creada",
                f"✅ Cuenta {cuenta.codigo} - {cuenta.nombre} creada correctamente."
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Error de validación", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 1: Plan de Cuentas
# ══════════════════════════════════════════════════════════════
class TabPUC(QWidget):
    def __init__(self, service: ContabilidadService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tb = QHBoxLayout()
        self.f_buscar = QLineEdit()
        self.f_buscar.setPlaceholderText("🔍  Buscar por código o nombre...")
        self.f_buscar.setFixedHeight(32)
        self.f_buscar.textChanged.connect(self._filtrar)

        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet("color:#64748b; font-size:12px;")

        btn_nueva = QPushButton("+ Nueva cuenta")
        btn_nueva.setStyleSheet(BTN_PRIMARY)
        btn_nueva.setFixedHeight(32)
        btn_nueva.clicked.connect(self._nueva_cuenta)

        tb.addWidget(self.f_buscar, stretch=1)
        tb.addWidget(self.lbl_total)
        tb.addWidget(btn_nueva)
        layout.addLayout(tb)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tabla = QTableWidget(1, 6)
        self.tabla.setHorizontalHeaderLabels(["Código", "Nombre", "Clase", "Naturaleza", "Módulo", "Mov."])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 110)
        self.tabla.setColumnWidth(1, 345)
        self.tabla.setColumnWidth(2, 90)
        self.tabla.setColumnWidth(3, 80)
        self.tabla.setColumnWidth(4, 100)
        self.tabla.setColumnWidth(5, 25)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Consolas", 10))
        self.tabla.itemDoubleClicked.connect(self._on_doble_clic)
        splitter.addWidget(self.tabla)

        # Panel derecho: visor de contenido PUC
        panel_contenido = QWidget()
        panel_contenido.setStyleSheet("background:#f8fafc;")
        pc_lay = QVBoxLayout(panel_contenido)
        pc_lay.setContentsMargins(10, 8, 10, 8)
        pc_lay.setSpacing(6)
        self.lbl_cuenta_titulo = QLabel("Doble clic en una cuenta para ver su descripción")
        self.lbl_cuenta_titulo.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_cuenta_titulo.setWordWrap(True)
        self.lbl_cuenta_titulo.setStyleSheet("color:#64748b;")
        pc_lay.addWidget(self.lbl_cuenta_titulo)
        self.txt_puc_contenido = QTextBrowser()
        self.txt_puc_contenido.setOpenLinks(False)
        self.txt_puc_contenido.anchorClicked.connect(self._on_link_puc)
        self.txt_puc_contenido.setStyleSheet(
            "background:white; border:1px solid #e2e8f0; border-radius:6px; "
            "font-size:12px; font-family:'Segoe UI',sans-serif; padding:6px;"
        )
        pc_lay.addWidget(self.txt_puc_contenido, stretch=1)
        splitter.addWidget(panel_contenido)

        splitter.setSizes([580, 200])
        layout.addWidget(splitter)

    def _cargar(self):
        self._cuentas = self.service.listar_puc()
        self._renderizar(self._cuentas)

    def _renderizar(self, cuentas):
        self.tabla.setRowCount(0)
        for c in cuentas:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)

            indent = "   " * (c.nivel - 1)
            nombre_item = QTableWidgetItem(f"{indent}{c.nombre}")
            codigo_item = QTableWidgetItem(c.codigo)

           #nivel_str = c.nivel_nombre.value.capitalize() if c.nivel_nombre else f"Nivel {c.nivel}"
            #nivel_item = QTableWidgetItem(nivel_str)

            clase_str = c.clase.value.capitalize() if c.clase else ""
            clase_item = QTableWidgetItem(clase_str)

            nat_val = c.naturaleza.value if hasattr(c.naturaleza, 'value') else str(c.naturaleza)
            nat_item = QTableWidgetItem("Débito" if nat_val == "debito" else "Crédito")

            mod_str = c.modulo.value.capitalize() if c.modulo else ""
            mod_item = QTableWidgetItem(mod_str)

            mov_item = QTableWidgetItem("✔" if c.acepta_mov else "")
            mov_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            clase = c.codigo[0] if c.codigo else "1"
            bg = QColor(COLOR_CLASE.get(clase, "#f8fafc"))

            if c.nivel <= 2:
                font = QFont("Consolas", 10, QFont.Weight.Bold)
                for item in [codigo_item, nombre_item, clase_item, nat_item]:
                    item.setFont(font)

            for col, item in enumerate([codigo_item, nombre_item, clase_item, nat_item, mod_item, mov_item]):
                if c.nivel <= 2:
                    item.setBackground(bg)
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self.tabla.setItem(r, col, item)

        self.lbl_total.setText(f"{len(cuentas)} cuentas")

    def _filtrar(self, texto: str):
        if not texto.strip():
            self._renderizar(self._cuentas)
            return
        t = texto.lower()
        filtradas = [
            c for c in self._cuentas
            if t in c.codigo.lower() or t in c.nombre.lower()
        ]
        self._renderizar(filtradas)

    def _nueva_cuenta(self):
        dlg = DialogNuevaCuenta(self.service, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._cargar()

    def _on_doble_clic(self, item):
        cuenta_id = item.data(Qt.ItemDataRole.UserRole)
        cuenta = next((c for c in self._cuentas if c.id == cuenta_id), None)
        if not cuenta:
            return
        self.mostrar_contenido_cuenta(cuenta)

    def mostrar_contenido_cuenta(self, cuenta):
        """Muestra el contenido HTML de la cuenta en el panel derecho."""
        contenido = self.service.obtener_contenido_puc(cuenta.codigo)
        nivel_str = cuenta.nivel_nombre.value if cuenta.nivel_nombre else f"nivel {cuenta.nivel}"
        titulo = f"{cuenta.codigo} — {cuenta.nombre}"
        self.lbl_cuenta_titulo.setText(titulo)
        self.lbl_cuenta_titulo.setStyleSheet("color:#1e293b;")

        if contenido:
            self.txt_puc_contenido.setHtml(contenido.contenido)
            return

        # Sin contenido: buscar la cuenta padre más cercana con contenido
        if cuenta.nivel <= 3:
            # Si es clase/grupo/cuenta y no tiene contenido, mostrar mensaje simple
            self.txt_puc_contenido.setHtml(
                "<p style='color:#94a3b8; font-style:italic;'>"
                "No hay descripción registrada para este código en el PUC.</p>"
            )
            return

        # Para subcuentas y auxiliares, buscar la cuenta padre con contenido
        padre_con_contenido = self._buscar_padre_con_contenido(cuenta.codigo)

        if cuenta.nivel == 4:
            tipo_str = "subcuentas"
            tipo_str1 = "subcuenta"
        else:
            tipo_str = "auxiliares"
            tipo_str1 = "auxiliar"

        if padre_con_contenido:
            padre_cuenta = next(
                (c for c in self._cuentas if c.codigo == padre_con_contenido.codigo), None
            )
            padre_nombre = padre_cuenta.nombre if padre_cuenta else padre_con_contenido.codigo
            html = (
                f"<p style='color:#374151;'>"
                f"La descripción y dinámica descritas en la reglamentación, solo van hasta las cuentas. "
                f"De manera que para saber cómo tratar las {tipo_str}, "
                f"hay que observar el comportamiento de la cuenta superior.</p>"
                f"<p style='color:#374151;'>En este caso; la {tipo_str1}: "
                f"<b>{cuenta.codigo} {cuenta.nombre}</b> "
                f"está dentro de la cuenta "
                f"<a href='puc:/{padre_con_contenido.codigo}' "
                f"style='color:#2563eb; font-weight:bold;'>"
                f"[{padre_con_contenido.codigo} {padre_nombre}]</a>. "
                f"Dale clic para observar su descripción y dinámica.</p>"
            )
        else:
            html = (
                f"<p style='color:#374151;'>"
                f"La descripción y dinámica descritas en la reglamentación, solo van hasta las cuentas. "
                f"De manera que para saber cómo tratar las {tipo_str}s o auxiliares, "
                f"hay que observar el comportamiento de la cuenta superior.</p>"
                f"<p style='color:#94a3b8; font-style:italic;'>"
                f"No se encontró una cuenta padre con contenido registrado en el PUC.</p>"
            )
        self.txt_puc_contenido.setHtml(html)

    def _buscar_padre_con_contenido(self, codigo: str):
        """
        Recorre prefijos del código de más largo a más corto hasta encontrar
        una entrada en puc_contenido. Ej: 133599 → 1335 → 133 → 13 → 1
        """
        for longitud in range(len(codigo) - 1, 0, -1):
            prefijo = codigo[:longitud]
            resultado = self.service.obtener_contenido_puc(prefijo)
            if resultado:
                return resultado
        return None

    def _on_link_puc(self, url):
        """Maneja clic en hipervínculo puc:/CODIGO → navega al contenido del padre."""
        if url.scheme() == "puc":
            # Qt parsea  puc:/1435  → scheme="puc", path="/1435"
            # por eso usamos path() y quitamos la barra inicial si la hay
            codigo_padre = url.path().lstrip("/")
            if not codigo_padre:
                codigo_padre = url.host()   # fallback por si cambia el comportamiento
            cuenta_padre = next((c for c in self._cuentas if c.codigo == codigo_padre), None)
            if cuenta_padre:
                self.mostrar_contenido_cuenta(cuenta_padre)
            else:
                # Cuenta no está en la lista cargada, pero sí hay contenido: mostrar directo
                contenido = self.service.obtener_contenido_puc(codigo_padre)
                if contenido:
                    self.lbl_cuenta_titulo.setText(f"{codigo_padre}")
                    self.lbl_cuenta_titulo.setStyleSheet("color:#1e293b;")
                    self.txt_puc_contenido.setHtml(contenido.contenido)

    def refresh(self):
        self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 2: Periodos Contables
# ══════════════════════════════════════════════════════════════
class TabPeriodos(QWidget):
    periodo_seleccionado = pyqtSignal(int)

    def __init__(self, service: ContabilidadService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grp = QGroupBox("Crear nuevo periodo")
        grp.setStyleSheet("QGroupBox { font-weight:bold; }")
        glay = QHBoxLayout(grp)

        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2000, 2100)
        self.spin_anio.setValue(date.today().year)
        self.spin_anio.setFixedWidth(90)

        self.combo_mes = QComboBox()
        for i, m in enumerate(MESES[1:], 1):
            self.combo_mes.addItem(m, i)
        self.combo_mes.setCurrentIndex(date.today().month - 1)
        self.combo_mes.setFixedWidth(130)

        btn_crear = QPushButton("+ Crear periodo")
        btn_crear.setStyleSheet(BTN_PRIMARY)
        btn_crear.clicked.connect(self._crear_periodo)

        glay.addWidget(QLabel("Año:"))
        glay.addWidget(self.spin_anio)
        glay.addWidget(QLabel("Mes:"))
        glay.addWidget(self.combo_mes)
        glay.addWidget(btn_crear)
        glay.addStretch()
        layout.addWidget(grp)

        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Año", "Mes", "Estado", "Acciones"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 70)
        self.tabla.setColumnWidth(2, 110)
        self.tabla.setColumnWidth(3, 140)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        layout.addWidget(self.tabla)

    def _cargar(self):
        self.tabla.setRowCount(0)
        periodos = self.service.listar_periodos()
        for p in periodos:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)

            anio_item = QTableWidgetItem(str(p.anio))
            anio_item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.tabla.setItem(r, 0, anio_item)
            self.tabla.setItem(r, 1, QTableWidgetItem(MESES[p.mes]))

            estado_item = QTableWidgetItem(
                "🟢 Abierto" if p.estado == EstadoPeriodo.ABIERTO else "🔒 Cerrado"
            )
            if p.estado == EstadoPeriodo.CERRADO:
                estado_item.setForeground(QColor("#CF3A3A"))
            else:
                estado_item.setForeground(QColor("#16a34a"))
            self.tabla.setItem(r, 2, estado_item)

            if p.estado == EstadoPeriodo.ABIERTO:
                btn = QPushButton("🔒 Cerrar periodo")
                btn.setStyleSheet("color:#dc2626; font-size:11px;")
                btn.clicked.connect(lambda _, pid=p.id: self._cerrar_periodo(pid))
                self.tabla.setCellWidget(r, 3, btn)
            else:
                self.tabla.setItem(r, 3, QTableWidgetItem(""))

    def _crear_periodo(self):
        anio = self.spin_anio.value()
        mes  = self.combo_mes.currentData()
        try:
            self.service.crear_periodo(anio, mes)
            self._cargar()
        except ValueError as e:
            QMessageBox.warning(self, "Aviso", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _cerrar_periodo(self, periodo_id: int):
        resp = QMessageBox.question(
            self, "Cerrar periodo",
            "¿Cerrar este periodo?\nNo podrás registrar asientos en él.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                self.service.cerrar_periodo(periodo_id)
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._cargar()

    def periodo_id_activo(self):
        for p in self.service.listar_periodos():
            if p.estado == EstadoPeriodo.ABIERTO:
                return p.id
        return None


# ══════════════════════════════════════════════════════════════
# Widget autocompletado de cuentas
# ══════════════════════════════════════════════════════════════
class CuentaSearchWidget(QWidget):
    """
    Campo de búsqueda de cuentas con autocompletado en tiempo real.

    El desplegable es un QFrame hijo del diálogo/ventana toplevel,
    NO una ventana flotante. Así nunca roba ni pierde el foco, y el
    usuario puede seguir escribiendo libremente mientras la lista
    se actualiza con cada tecla.
    """
    cuenta_seleccionada = pyqtSignal(object)

    def __init__(self, service: ContabilidadService, parent=None):
        super().__init__(parent)
        self.service = service
        self._cuenta = None
        self._seleccionando = False
        self._popup_frame = None   # se crea lazy al primer uso

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Código o nombre...")
        self.edit.textChanged.connect(self._on_text_changed)
        lay.addWidget(self.edit)

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._buscar)

    def _get_popup(self):
        """Crea el QFrame popup la primera vez, anclado a la ventana toplevel."""
        if self._popup_frame is not None:
            return self._popup_frame

        top = self.window()

        frame = QFrame(top)
        frame.setStyleSheet(
            "QFrame { border:2px solid #2563eb; background:white; border-radius:4px; }"
        )
        frame.hide()

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        lista = QListWidget()
        lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lista.setStyleSheet(
            "QListWidget { border:none; background:white; font-size:12px; color:#111111; }"
            "QListWidget::item { color:#111111; padding:4px 8px; }"
            "QListWidget::item:hover { background:#eff6ff; color:#1e3a8a; }"
            "QListWidget::item:selected { background:#dbeafe; color:#1e3a8a; }"
        )
        lista.itemClicked.connect(self._on_item_clicked)
        fl.addWidget(lista)

        frame._lista = lista
        self._popup_frame = frame
        return frame

    def _on_text_changed(self, text):
        if self._seleccionando:
            return
        if not text.strip():
            self._cuenta = None
            self.edit.setStyleSheet("")
            self._ocultar_popup()
            return
        if self._cuenta is not None:
            self._cuenta = None
            self.edit.setStyleSheet("")
        self._timer.start()

    def _buscar(self):
        texto = self.edit.text().strip()
        if not texto:
            return
        cuentas = self.service.buscar_cuentas(texto, solo_movibles=True)

        popup = self._get_popup()
        popup._lista.clear()

        if not cuentas:
            self._ocultar_popup()
            return

        for c in cuentas[:25]:
            item = QListWidgetItem(f"{c.codigo}  —  {c.nombre}")
            item.setForeground(QColor("#111111"))
            item.setData(Qt.ItemDataRole.UserRole, c)
            popup._lista.addItem(item)

        # Mapear posición inferior del edit al sistema de coordenadas del toplevel
        top = self.window()
        global_pos = self.edit.mapToGlobal(self.edit.rect().bottomLeft())
        local_pos  = top.mapFromGlobal(global_pos)

        ancho = max(self.edit.width(), 460)
        alto  = min(len(cuentas) * 28 + 4, 260)
        popup.setGeometry(local_pos.x(), local_pos.y(), ancho, alto)
        popup.raise_()
        popup.show()

    def _ocultar_popup(self):
        if self._popup_frame is not None:
            self._popup_frame.hide()

    def _on_item_clicked(self, item):
        cuenta = item.data(Qt.ItemDataRole.UserRole)
        self._cuenta = cuenta
        self._seleccionando = True
        self.edit.setText(f"{cuenta.codigo}  —  {cuenta.nombre}")
        self.edit.setStyleSheet("border:1px solid #16a34a; color:#111111;")
        self._seleccionando = False
        self._ocultar_popup()
        self.cuenta_seleccionada.emit(cuenta)

    def hideEvent(self, event):
        self._ocultar_popup()
        super().hideEvent(event)

    def get_cuenta(self):
        return self._cuenta

    def reset(self):
        self._seleccionando = True
        self.edit.clear()
        self._seleccionando = False
        self.edit.setStyleSheet("")
        self._cuenta = None
        self._ocultar_popup()


# ══════════════════════════════════════════════════════════════
# Diálogo: Nuevo Asiento
# ══════════════════════════════════════════════════════════════
class DialogNuevoAsiento(QDialog):
    def __init__(self, service: ContabilidadService, periodo_id: int, parent=None):
        super().__init__(parent)
        self.service    = service
        self.periodo_id = periodo_id
        self.setWindowTitle("Nuevo asiento contable")
        self.setMinimumSize(1050, 640)
        self._build_ui()
        self._agregar_fila()
        self._agregar_fila()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ── Barra superior ────────────────────────────────────────
        top_bar = QHBoxLayout()
        titulo = QLabel("📝 Nuevo Asiento Contable")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b;")
        top_bar.addWidget(titulo)
        top_bar.addStretch()
        btn_puc = QPushButton("📋 Consultar Plan de Cuentas")
        btn_puc.setToolTip("Abre el plan de cuentas sin cerrar esta ventana")
        btn_puc.setStyleSheet(
            "background:#f1f5f9; color:#1e293b; padding:5px 12px; "
            "border:1px solid #cbd5e1; border-radius:5px; font-size:12px;"
        )
        btn_puc.clicked.connect(self._abrir_consulta_puc)
        top_bar.addWidget(btn_puc)
        layout.addLayout(top_bar)

        # ── Cabecera del asiento ──────────────────────────────────
        cab = QHBoxLayout()
        self.f_fecha = QDateEdit(QDate.currentDate())
        self.f_fecha.setCalendarPopup(True)
        self.f_fecha.setFixedWidth(130)
        self.f_desc = QLineEdit()
        self.f_desc.setPlaceholderText("Descripción del asiento...")

        self.cb_fuente = QComboBox()
        self.cb_fuente.setFixedWidth(200)
        self.cb_fuente.addItem("— Sin fuente —", None)
        try:
            for f in self.service.listar_fuentes():
                self.cb_fuente.addItem(f"{f.codigo} - {f.descripcion}", f.id)
        except Exception:
            pass

        cab.addWidget(QLabel("Fecha:"))
        cab.addWidget(self.f_fecha)
        cab.addWidget(QLabel("Fuente:"))
        cab.addWidget(self.cb_fuente)
        cab.addWidget(QLabel("Descripción:"))
        cab.addWidget(self.f_desc, 1)
        layout.addLayout(cab)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        layout.addWidget(sep)

        lbl_mov = QLabel("Movimientos")
        lbl_mov.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_mov)

        # ── Tabla movimientos (5 columnas) ────────────────────────
        # Col 0: Cuenta (widget CuentaSearchWidget — muestra "código — nombre")
        # Col 1: Tercero
        # Col 2: Descripción línea
        # Col 3: Débito
        # Col 4: Crédito
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(
            ["Cuenta", "Tercero", "Descripción línea", "Débito", "Crédito"]
        )
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tbl.setColumnWidth(1, 150)
        self.tbl.setColumnWidth(2, 190)
        self.tbl.setColumnWidth(3, 115)
        self.tbl.setColumnWidth(4, 115)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setAlternatingRowColors(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tbl)

        tb_mov = QHBoxLayout()
        btn_add = QPushButton("+ Agregar fila")
        btn_add.clicked.connect(self._agregar_fila)
        btn_del = QPushButton("🗑 Eliminar fila")
        btn_del.clicked.connect(self._eliminar_fila)
        btn_del.setStyleSheet("color:#dc2626;")
        tb_mov.addWidget(btn_add)
        tb_mov.addWidget(btn_del)
        tb_mov.addStretch()
        layout.addLayout(tb_mov)

        tots = QHBoxLayout()
        tots.addStretch()
        self.lbl_total_db = QLabel("Débitos: $0.00")
        self.lbl_total_db.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_total_db.setStyleSheet("color:#1d4ed8;")
        self.lbl_total_cr = QLabel("Créditos: $0.00")
        self.lbl_total_cr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_total_cr.setStyleSheet("color:#16a34a;")
        self.lbl_diff = QLabel("")
        self.lbl_diff.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        tots.addWidget(self.lbl_total_db)
        tots.addWidget(QLabel("  |  "))
        tots.addWidget(self.lbl_total_cr)
        tots.addWidget(QLabel("  "))
        tots.addWidget(self.lbl_diff)
        layout.addLayout(tots)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#e2e8f0;")
        layout.addWidget(sep2)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        self.btn_guardar = QPushButton("💾 Guardar asiento")
        self.btn_guardar.setFixedWidth(170)
        self.btn_guardar.setStyleSheet(BTN_PRIMARY)
        self.btn_guardar.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_guardar)
        layout.addLayout(btns)

        self.tbl.cellChanged.connect(self._on_cell_changed)

    def _abrir_consulta_puc(self):
        """Abre el plan de cuentas en una ventana flotante sin cerrar el asiento."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Plan de Cuentas — Consulta")
        dlg.setMinimumSize(1000, 600)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        tab_puc = TabPUC(self.service, dlg)
        lay.addWidget(tab_puc)
        dlg.exec()

    def _agregar_fila(self):
        self.tbl.blockSignals(True)
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        # Col 0: búsqueda de cuenta (muestra "código — nombre" al seleccionar)
        search_w = CuentaSearchWidget(self.service)
        search_w.cuenta_seleccionada.connect(
            lambda cuenta, row=r: self._on_cuenta_seleccionada(row, cuenta)
        )
        self.tbl.setCellWidget(r, 0, search_w)

        # Col 1: tercero
        tercero_edit = QLineEdit()
        tercero_edit.setPlaceholderText("NIT o nombre...")
        self.tbl.setCellWidget(r, 1, tercero_edit)

        # Col 2: descripción línea
        self.tbl.setItem(r, 2, QTableWidgetItem(""))

        # Col 3: débito
        db_item = QTableWidgetItem("0.00")
        db_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl.setItem(r, 3, db_item)


        # Col 4: crédito
        cr_item = QTableWidgetItem("0.00")
        cr_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl.setItem(r, 4, cr_item)

        self.tbl.setRowHeight(r, 36)
        self.tbl.blockSignals(False)

    def _on_cuenta_seleccionada(self, row, cuenta):
        # La columna Cuenta ya muestra "código — nombre" dentro del CuentaSearchWidget.
        # No hay columna separada de nombre, nada más que hacer aquí.
        pass

    def _eliminar_fila(self):
        fila = self.tbl.currentRow()
        if fila >= 0 and self.tbl.rowCount() > 1:
            self.tbl.removeRow(fila)
            self._actualizar_totales()

    def _on_cell_changed(self, row, col):
        if col in (3, 4):   # débito=3, crédito=4
            self._actualizar_totales()

    def _actualizar_totales(self):
        self.tbl.blockSignals(True)
        total_db = Decimal("0")
        total_cr = Decimal("0")
        for r in range(self.tbl.rowCount()):
            try:
                db_item = self.tbl.item(r, 3)
                cr_item = self.tbl.item(r, 4)
                if db_item:
                    total_db += Decimal(db_item.text().replace(",", ".") or "0")
                if cr_item:
                    total_cr += Decimal(cr_item.text().replace(",", ".") or "0")
            except InvalidOperation:
                pass

        self.lbl_total_db.setText(f"Débitos: ${total_db:,.2f}")
        self.lbl_total_cr.setText(f"Créditos: ${total_cr:,.2f}")

        diff = total_db - total_cr
        if diff == 0 and total_db > 0:
            self.lbl_diff.setText("✅ Cuadra")
            self.lbl_diff.setStyleSheet("color:#16a34a; font-weight:bold;")
        elif diff != 0:
            self.lbl_diff.setText(f"⚠ Diferencia: ${abs(diff):,.2f}")
            self.lbl_diff.setStyleSheet("color:#dc2626; font-weight:bold;")
        else:
            self.lbl_diff.setText("")
        self.tbl.blockSignals(False)

    def _guardar(self):
        if not self.f_desc.text().strip():
            QMessageBox.warning(self, "Falta descripción", "Ingresa una descripción para el asiento.")
            return

        lineas = []
        for r in range(self.tbl.rowCount()):
            sw = self.tbl.cellWidget(r, 0)
            cuenta = sw.get_cuenta() if sw else None
            if not cuenta:
                continue
            try:
                db_text = self.tbl.item(r, 3).text().replace(",", ".") if self.tbl.item(r, 3) else "0"
                cr_text = self.tbl.item(r, 4).text().replace(",", ".") if self.tbl.item(r, 4) else "0"
                debito  = Decimal(db_text or "0")
                credito = Decimal(cr_text or "0")
            except InvalidOperation:
                QMessageBox.warning(self, "Valor inválido", f"Fila {r+1}: valor numérico inválido.")
                return

            desc_item = self.tbl.item(r, 2)
            lineas.append({
                "cuenta_id":   cuenta.id,
                "debito":      debito,
                "credito":     credito,
                "descripcion": desc_item.text() if desc_item else "",
            })

        if not lineas:
            QMessageBox.warning(self, "Sin movimientos", "Agrega al menos una línea con cuenta válida.")
            return

        qdate = self.f_fecha.date()
        fecha = date(qdate.year(), qdate.month(), qdate.day())

        try:
            asiento = self.service.crear_asiento(
                periodo_id  = self.periodo_id,
                fecha       = fecha,
                descripcion = self.f_desc.text().strip(),
                lineas      = lineas,
                fuente_id   = self.cb_fuente.currentData(),
            )
            QMessageBox.information(
                self, "Asiento guardado",
                f"✅ Asiento {asiento.numero} registrado correctamente."
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Error de validación", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 3: Libro Diario / Asientos
# ══════════════════════════════════════════════════════════════
class TabAsientos(QWidget):
    def __init__(self, service: ContabilidadService, get_periodo_fn, parent=None):
        super().__init__(parent)
        self.service     = service
        self.get_periodo = get_periodo_fn
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tb = QHBoxLayout()
        self.combo_periodo = QComboBox()
        self.combo_periodo.setFixedWidth(200)
        self.combo_periodo.currentIndexChanged.connect(self._cargar)
        self._llenar_periodos()

        btn_nuevo = QPushButton("+ Nuevo asiento")
        btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.clicked.connect(self._nuevo_asiento)

        btn_anular = QPushButton("🚫 Anular")
        btn_anular.setStyleSheet("color:#dc2626;")
        btn_anular.clicked.connect(self._anular_asiento)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(36)
        btn_refresh.clicked.connect(self._cargar)

        tb.addWidget(QLabel("Periodo:"))
        tb.addWidget(self.combo_periodo)
        tb.addWidget(btn_nuevo)
        tb.addWidget(btn_anular)
        tb.addStretch()
        tb.addWidget(btn_refresh)
        layout.addLayout(tb)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.tbl_asientos = QTableWidget(0, 6)
        self.tbl_asientos.setHorizontalHeaderLabels(
            ["Número", "Fecha", "Descripción", "Fuente", "Estado", "Total"]
        )
        hh = self.tbl_asientos.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_asientos.setColumnWidth(0, 90)
        self.tbl_asientos.setColumnWidth(1, 100)
        self.tbl_asientos.setColumnWidth(3, 130)
        self.tbl_asientos.setColumnWidth(4, 100)
        self.tbl_asientos.setColumnWidth(5, 110)
        self.tbl_asientos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_asientos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_asientos.verticalHeader().setVisible(False)
        self.tbl_asientos.setAlternatingRowColors(False)
        self.tbl_asientos.itemSelectionChanged.connect(self._on_asiento_sel)
        splitter.addWidget(self.tbl_asientos)

        grp = QGroupBox("Movimientos del asiento seleccionado")
        grp.setStyleSheet("QGroupBox { font-weight:bold; }")
        glay = QVBoxLayout(grp)
        self.tbl_movs = QTableWidget(0, 5)
        self.tbl_movs.setHorizontalHeaderLabels(["Cuenta", "Nombre cuenta", "Tercero", "Débito", "Crédito"])
        hh2 = self.tbl_movs.horizontalHeader()
        hh2.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_movs.setColumnWidth(0, 110)
        self.tbl_movs.setColumnWidth(2, 150)
        self.tbl_movs.setColumnWidth(3, 120)
        self.tbl_movs.setColumnWidth(4, 120)
        self.tbl_movs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_movs.verticalHeader().setVisible(False)
        self.tbl_movs.setAlternatingRowColors(False)
        glay.addWidget(self.tbl_movs)
        splitter.addWidget(grp)

        splitter.setSizes([320, 200])
        layout.addWidget(splitter)

    def _llenar_periodos(self):
        self.combo_periodo.blockSignals(True)
        self.combo_periodo.clear()
        self.combo_periodo.addItem("Todos los periodos", None)
        for p in self.service.listar_periodos():
            label = f"{MESES[p.mes]} {p.anio}"
            if p.estado == EstadoPeriodo.ABIERTO:
                label += " 🟢"
            self.combo_periodo.addItem(label, p.id)
        self.combo_periodo.blockSignals(False)

    def _cargar(self):
        periodo_id = self.combo_periodo.currentData()
        asientos   = self.service.listar_asientos(periodo_id=periodo_id)
        self.tbl_asientos.setRowCount(0)
        for a in asientos:
            r = self.tbl_asientos.rowCount()
            self.tbl_asientos.insertRow(r)

            num_item = QTableWidgetItem(a.numero)
            num_item.setData(Qt.ItemDataRole.UserRole, a.id)
            self.tbl_asientos.setItem(r, 0, num_item)
            self.tbl_asientos.setItem(r, 1, QTableWidgetItem(str(a.fecha)))
            self.tbl_asientos.setItem(r, 2, QTableWidgetItem(a.descripcion or ""))

            fuente_str = ""
            if hasattr(a, "fuente") and a.fuente:
                fuente_str = f"{a.fuente.codigo} - {a.fuente.descripcion}"
            self.tbl_asientos.setItem(r, 3, QTableWidgetItem(fuente_str))

            estado_val = a.estado.value if hasattr(a.estado, 'value') else str(a.estado)
            estado_item = QTableWidgetItem(estado_val.capitalize())
            if a.estado == EstadoAsiento.ANULADO:
                estado_item.setForeground(QColor("#dc2626"))
            self.tbl_asientos.setItem(r, 4, estado_item)

            total = sum(m.debito for m in a.movimientos)
            total_item = QTableWidgetItem(f"${total:,.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_asientos.setItem(r, 5, total_item)

            if a.estado == EstadoAsiento.ANULADO:
                for col in range(6):
                    item = self.tbl_asientos.item(r, col)
                    if item:
                        item.setForeground(QColor("#94a3b8"))

        self.tbl_movs.setRowCount(0)

    def _on_asiento_sel(self):
        fila = self.tbl_asientos.currentRow()
        if fila < 0:
            return
        item_num = self.tbl_asientos.item(fila, 0)
        if not item_num:
            return
        asiento_id = item_num.data(Qt.ItemDataRole.UserRole)
        asiento    = self.service.obtener_asiento(asiento_id)
        if not asiento:
            return
        self.tbl_movs.setRowCount(0)
        for m in asiento.movimientos:
            r = self.tbl_movs.rowCount()
            self.tbl_movs.insertRow(r)
            self.tbl_movs.setItem(r, 0, QTableWidgetItem(m.cuenta.codigo if m.cuenta else ""))
            self.tbl_movs.setItem(r, 1, QTableWidgetItem(m.cuenta.nombre if m.cuenta else ""))

            tercero_str = ""
            if m.tercero:
                tercero_str = getattr(m.tercero, "nombre", "") or getattr(m.tercero, "razon_social", "")
            self.tbl_movs.setItem(r, 2, QTableWidgetItem(tercero_str))

            db_item = QTableWidgetItem(f"${m.debito:,.2f}" if m.debito else "")
            cr_item = QTableWidgetItem(f"${m.credito:,.2f}" if m.credito else "")
            db_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cr_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            db_item.setForeground(QColor("#1d4ed8"))
            cr_item.setForeground(QColor("#16a34a"))
            self.tbl_movs.setItem(r, 3, db_item)
            self.tbl_movs.setItem(r, 4, cr_item)

    def _nuevo_asiento(self):
        periodo_id = self.get_periodo()
        if not periodo_id:
            QMessageBox.warning(
                self, "Sin periodo activo",
                "No hay un periodo contable abierto.\n"
                "Ve a la pestaña 'Periodos' y crea uno."
            )
            return
        dlg = DialogNuevoAsiento(self.service, periodo_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._llenar_periodos()
            self._cargar()

    def _anular_asiento(self):
        fila = self.tbl_asientos.currentRow()
        if fila < 0:
            return
        asiento_id = self.tbl_asientos.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        numero     = self.tbl_asientos.item(fila, 0).text()
        resp = QMessageBox.question(
            self, "Confirmar anulación",
            f"¿Anular el asiento {numero}?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                self.service.anular_asiento(asiento_id)
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._llenar_periodos()
        self._cargar()


# ══════════════════════════════════════════════════════════════
# Widget principal del módulo Contabilidad
# ══════════════════════════════════════════════════════════════
class ContabilidadWidget(QWidget):
