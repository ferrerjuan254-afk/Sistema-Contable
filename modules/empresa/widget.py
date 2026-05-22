from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QSplitter, QGroupBox, QHeaderView,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QFont, QRegularExpressionValidator

from core.database import SessionLocal
from core.models.empresa import Sede
from modules.empresa.service import EmpresaService


# ══════════════════════════════════════════════════════════════
# Diálogo: Crear / Editar Empresa
# ══════════════════════════════════════════════════════════════
class DialogEmpresa(QDialog):
    def __init__(self, parent=None, empresa=None):
        super().__init__(parent)
        self.empresa = empresa
        self.setWindowTitle("Nueva empresa" if not empresa else "Editar empresa")
        self.setMinimumWidth(500)
        self._build_ui()
        if empresa:
            self._cargar_datos()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        # Razón social
        self.f_razon = QLineEdit()
        self.f_razon.setPlaceholderText("Nombre completo o razón social")

        # NIT + DV en una misma fila
        nit_row = QHBoxLayout()
        nit_row.setSpacing(6)
        self.f_nit = QLineEdit()
        self.f_nit.setPlaceholderText("Ej: 900123456")
        self.f_nit.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\d{0,15}$"))
        )
        separador = QLabel("-")
        separador.setFixedWidth(10)
        separador.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separador.setStyleSheet("color:#64748b; font-weight:bold; font-size:14px;")
        self.f_dv = QLineEdit()
        self.f_dv.setPlaceholderText("DV")
        self.f_dv.setFixedWidth(48)
        self.f_dv.setMaxLength(1)
        self.f_dv.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\d?$"))
        )
        self.f_dv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nit_row.addWidget(self.f_nit, stretch=1)
        nit_row.addWidget(separador)
        nit_row.addWidget(self.f_dv)

        self.f_ciudad   = QLineEdit(); self.f_ciudad.setPlaceholderText("Ciudad")
        self.f_dir      = QLineEdit(); self.f_dir.setPlaceholderText("Dirección")
        self.f_tel      = QLineEdit(); self.f_tel.setPlaceholderText("Teléfono")
        self.f_email    = QLineEdit(); self.f_email.setPlaceholderText("correo@empresa.com")
        self.f_repre    = QLineEdit(); self.f_repre.setPlaceholderText("Nombre del representante legal")

        form.addRow("Razón social *",      self.f_razon)
        form.addRow("NIT * — DV *",        nit_row)
        form.addRow("Ciudad",              self.f_ciudad)
        form.addRow("Dirección",           self.f_dir)
        form.addRow("Teléfono",            self.f_tel)
        form.addRow("Email",               self.f_email)
        form.addRow("Representante legal", self.f_repre)
        layout.addLayout(form)

        if not self.empresa:
            nota = QLabel(
                "ℹ️  Al crear la empresa se cargará automáticamente el PUC "
                "colombiano y se creará la sede principal."
            )
            nota.setWordWrap(True)
            nota.setStyleSheet(
                "color:#64748b; font-size:12px; background:#f1f5f9; "
                "padding:8px; border-radius:6px;"
            )
            layout.addWidget(nota)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar" if self.empresa else "Crear empresa")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(
            "background:#2563eb; color:white; padding:6px 20px; border-radius:6px;"
        )
        btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _cargar_datos(self):
        e = self.empresa
        self.f_razon.setText(e.razon_social  or "")
        self.f_nit.setText(e.nit             or "")
        self.f_dv.setText(e.dv               or "")
        self.f_ciudad.setText(e.ciudad       or "")
        self.f_dir.setText(e.direccion       or "")
        self.f_tel.setText(e.telefono        or "")
        self.f_email.setText(e.email         or "")
        self.f_repre.setText(e.representante or "")

    def _guardar(self):
        if not self.f_razon.text().strip():
            QMessageBox.warning(self, "Campo requerido", "La razón social es obligatoria.")
            self.f_razon.setFocus()
            return
        if not self.f_nit.text().strip():
            QMessageBox.warning(self, "Campo requerido", "El NIT es obligatorio.")
            self.f_nit.setFocus()
            return
        if not self.f_dv.text().strip():
            QMessageBox.warning(self, "Campo requerido", "El dígito de verificación es obligatorio.")
            self.f_dv.setFocus()
            return
        self.accept()

    def datos(self) -> dict:
        return {
            "razon_social":  self.f_razon.text().strip(),
            "nit":           self.f_nit.text().strip(),
            "dv":            self.f_dv.text().strip(),
            "ciudad":        self.f_ciudad.text().strip(),
            "direccion":     self.f_dir.text().strip(),
            "telefono":      self.f_tel.text().strip(),
            "email":         self.f_email.text().strip(),
            "representante": self.f_repre.text().strip(),
        }


# ══════════════════════════════════════════════════════════════
# Diálogo: Crear / Editar Sede
# ══════════════════════════════════════════════════════════════
class DialogSede(QDialog):
    def __init__(self, parent=None, sede=None):
        super().__init__(parent)
        self.sede = sede
        self.setWindowTitle("Nueva sede" if not sede else "Editar sede")
        self.setMinimumWidth(400)
        self._build_ui()
        if sede:
            self._cargar_datos()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.f_nombre = QLineEdit(); self.f_nombre.setPlaceholderText("Nombre de la sede")
        self.f_ciudad = QLineEdit(); self.f_ciudad.setPlaceholderText("Ciudad")
        self.f_dir    = QLineEdit(); self.f_dir.setPlaceholderText("Dirección")
        self.f_tel    = QLineEdit(); self.f_tel.setPlaceholderText("Teléfono")

        form.addRow("Nombre *",  self.f_nombre)
        form.addRow("Ciudad",    self.f_ciudad)
        form.addRow("Dirección", self.f_dir)
        form.addRow("Teléfono",  self.f_tel)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        QPushButton("Cancelar", clicked=self.reject).setParent(None)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(
            "background:#2563eb; color:white; padding:6px 20px; border-radius:6px;"
        )
        btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _cargar_datos(self):
        self.f_nombre.setText(self.sede.nombre    or "")
        self.f_ciudad.setText(self.sede.ciudad    or "")
        self.f_dir.setText(self.sede.direccion    or "")
        self.f_tel.setText(self.sede.telefono     or "")

    def _guardar(self):
        if not self.f_nombre.text().strip():
            QMessageBox.warning(self, "Campo requerido", "El nombre de la sede es obligatorio.")
            return
        self.accept()

    def datos(self) -> dict:
        return {
            "nombre":    self.f_nombre.text().strip(),
            "ciudad":    self.f_ciudad.text().strip(),
            "direccion": self.f_dir.text().strip(),
            "telefono":  self.f_tel.text().strip(),
        }


# ══════════════════════════════════════════════════════════════
# Panel principal del módulo Empresas
# ══════════════════════════════════════════════════════════════
class EmpresasWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session         = SessionLocal()
        self.service         = EmpresaService(self.session)
        self.empresa_sel_id  = None
        self._sedes          = []
        self._build_ui()
        self._cargar_empresas()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        titulo = QLabel("🏢  Empresas y Sedes")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b;")
        root.addWidget(titulo)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Empresas ───────────────────────────────────────────
        left = QGroupBox("Empresas")
        left.setStyleSheet("QGroupBox { font-weight:bold; }")
        lv = QVBoxLayout(left)

        tb = QHBoxLayout()
        self.btn_nueva_emp   = QPushButton("+ Nueva empresa")
        self.btn_nueva_emp.setStyleSheet(
            "background:#2563eb; color:white; padding:5px 14px; border-radius:5px;"
        )
        self.btn_nueva_emp.clicked.connect(self._nueva_empresa)
        self.btn_editar_emp  = QPushButton("✏️ Editar")
        self.btn_editar_emp.setEnabled(False)
        self.btn_editar_emp.clicked.connect(self._editar_empresa)
        self.btn_elim_emp    = QPushButton("🗑️ Eliminar")
        self.btn_elim_emp.setEnabled(False)
        self.btn_elim_emp.setStyleSheet("color:#dc2626;")
        self.btn_elim_emp.clicked.connect(self._eliminar_empresa)
        tb.addWidget(self.btn_nueva_emp)
        tb.addWidget(self.btn_editar_emp)
        tb.addWidget(self.btn_elim_emp)
        tb.addStretch()
        lv.addLayout(tb)

        self.tbl_emp = QTableWidget(0, 3)
        self.tbl_emp.setHorizontalHeaderLabels(["NIT", "Razón Social", "Ciudad"])
        self.tbl_emp.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_emp.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_emp.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_emp.setAlternatingRowColors(True)
        self.tbl_emp.verticalHeader().setVisible(False)
        self.tbl_emp.itemSelectionChanged.connect(self._on_empresa_sel)
        lv.addWidget(self.tbl_emp)
        splitter.addWidget(left)

        # ── Sedes ──────────────────────────────────────────────
        right = QGroupBox("Sedes de la empresa seleccionada")
        right.setStyleSheet("QGroupBox { font-weight:bold; }")
        rv = QVBoxLayout(right)

        tb2 = QHBoxLayout()
        self.btn_nueva_sede  = QPushButton("+ Nueva sede")
        self.btn_nueva_sede.setEnabled(False)
        self.btn_nueva_sede.setStyleSheet(
            "background:#059669; color:white; padding:5px 14px; border-radius:5px;"
        )
        self.btn_nueva_sede.clicked.connect(self._nueva_sede)
        self.btn_editar_sede = QPushButton("✏️ Editar")
        self.btn_editar_sede.setEnabled(False)
        self.btn_editar_sede.clicked.connect(self._editar_sede)
        self.btn_elim_sede   = QPushButton("🗑️ Eliminar")
        self.btn_elim_sede.setEnabled(False)
        self.btn_elim_sede.setStyleSheet("color:#dc2626;")
        self.btn_elim_sede.clicked.connect(self._eliminar_sede)
        tb2.addWidget(self.btn_nueva_sede)
        tb2.addWidget(self.btn_editar_sede)
        tb2.addWidget(self.btn_elim_sede)
        tb2.addStretch()
        rv.addLayout(tb2)

        self.tbl_sedes = QTableWidget(0, 3)
        self.tbl_sedes.setHorizontalHeaderLabels(["Nombre", "Ciudad", "Dirección"])
        self.tbl_sedes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_sedes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_sedes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_sedes.setAlternatingRowColors(True)
        self.tbl_sedes.verticalHeader().setVisible(False)
        self.tbl_sedes.itemSelectionChanged.connect(self._on_sede_sel)
        rv.addWidget(self.tbl_sedes)
        splitter.addWidget(right)

        splitter.setSizes([450, 450])
        root.addWidget(splitter)

    # ── Datos ──────────────────────────────────────────────────

    def _cargar_empresas(self):
        self.tbl_emp.setRowCount(0)
        self._empresas = self.service.listar()
        for emp in self._empresas:
            r = self.tbl_emp.rowCount()
            self.tbl_emp.insertRow(r)
            item_nit = QTableWidgetItem(emp.nit_completo)
            item_nit.setData(Qt.ItemDataRole.UserRole, emp.id)
            self.tbl_emp.setItem(r, 0, item_nit)
            self.tbl_emp.setItem(r, 1, QTableWidgetItem(emp.razon_social))
            self.tbl_emp.setItem(r, 2, QTableWidgetItem(emp.ciudad or ""))

    def _cargar_sedes(self, empresa_id: int):
        self.tbl_sedes.setRowCount(0)
        self._sedes = self.service.listar_sedes(empresa_id)
        for sede in self._sedes:
            r = self.tbl_sedes.rowCount()
            self.tbl_sedes.insertRow(r)
            item = QTableWidgetItem(sede.nombre)
            item.setData(Qt.ItemDataRole.UserRole, sede.id)
            self.tbl_sedes.setItem(r, 0, item)
            self.tbl_sedes.setItem(r, 1, QTableWidgetItem(sede.ciudad    or ""))
            self.tbl_sedes.setItem(r, 2, QTableWidgetItem(sede.direccion or ""))

    # ── Selección ──────────────────────────────────────────────

    def _on_empresa_sel(self):
        tiene = bool(self.tbl_emp.selectedItems())
        self.btn_editar_emp.setEnabled(tiene)
        self.btn_elim_emp.setEnabled(tiene)
        self.btn_nueva_sede.setEnabled(tiene)
        if tiene:
            fila = self.tbl_emp.currentRow()
            self.empresa_sel_id = self.tbl_emp.item(fila, 0).data(Qt.ItemDataRole.UserRole)
            self._cargar_sedes(self.empresa_sel_id)
        else:
            self.empresa_sel_id = None
            self.tbl_sedes.setRowCount(0)

    def _on_sede_sel(self):
        tiene = bool(self.tbl_sedes.selectedItems())
        self.btn_editar_sede.setEnabled(tiene)
        self.btn_elim_sede.setEnabled(tiene)

    # ── Acciones Empresa ───────────────────────────────────────

    def _nueva_empresa(self):
        dlg = DialogEmpresa(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                emp = self.service.crear(dlg.datos())
                self._cargar_empresas()
                QMessageBox.information(
                    self, "Empresa creada",
                    f"✅ '{emp.razon_social}' creada correctamente.\n"
                    f"NIT: {emp.nit_completo}\n"
                    f"PUC cargado y sede principal creada."
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo crear la empresa:\n{e}")

    def _editar_empresa(self):
        if not self.empresa_sel_id:
            return
        empresa = self.service.obtener(self.empresa_sel_id)
        dlg = DialogEmpresa(self, empresa=empresa)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar(self.empresa_sel_id, dlg.datos())
                self._cargar_empresas()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo actualizar:\n{e}")

    def _eliminar_empresa(self):
        if not self.empresa_sel_id:
            return
        empresa = self.service.obtener(self.empresa_sel_id)
        resp = QMessageBox.question(
            self, "Confirmar",
            f"¿Desactivar '{empresa.razon_social}'?\nLos datos no se borrarán.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.service.desactivar(self.empresa_sel_id)
            self._cargar_empresas()

    # ── Acciones Sede ──────────────────────────────────────────

    def _nueva_sede(self):
        if not self.empresa_sel_id:
            return
        dlg = DialogSede(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_sede(self.empresa_sel_id, dlg.datos())
                self._cargar_sedes(self.empresa_sel_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo crear la sede:\n{e}")

    def _editar_sede(self):
        fila = self.tbl_sedes.currentRow()
        if fila < 0:
            return
        sede_id = self.tbl_sedes.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        sede = self.session.get(Sede, sede_id)
        dlg = DialogSede(self, sede=sede)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar_sede(sede_id, dlg.datos())
                self._cargar_sedes(self.empresa_sel_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo actualizar:\n{e}")

    def _eliminar_sede(self):
        fila = self.tbl_sedes.currentRow()
        if fila < 0:
            return
        sede_id  = self.tbl_sedes.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        nombre   = self.tbl_sedes.item(fila, 0).text()
        resp = QMessageBox.question(
            self, "Confirmar",
            f"¿Desactivar la sede '{nombre}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.service.desactivar_sede(sede_id)
            self._cargar_sedes(self.empresa_sel_id)

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)
