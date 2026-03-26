from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QPushButton, QDialog, QLineEdit,
    QListWidget, QListWidgetItem, QCheckBox, QDialogButtonBox,
)
from PySide6.QtCore  import Qt, Signal
from PySide6.QtGui   import QKeySequence, QShortcut

from translation_store import (
    TranslationStore,
    STATUS_UNTRANSLATED, STATUS_DRAFT, STATUS_REVIEWED,
    STATUS_LABELS, STATUS_CYCLE
)

STATUS_BUTTON_STYLES = {
    STATUS_UNTRANSLATED: "background:#E57373; color:#111; border-radius:4px; padding:4px 10px;",
    STATUS_DRAFT:        "background:#FFB74D; color:#111; border-radius:4px; padding:4px 10px;",
    STATUS_REVIEWED:     "background:#81C784; color:#111; border-radius:4px; padding:4px 10px;",
}

CONTEXT_WINDOW = 5  

class EditorPanel(QWidget):
    """
    Panel derecho de edición de traducciones.

    Señales:
        translation_changed(int line_index, str new_text)
            → emitida cuando el usuario modifica el texto de la traducción
        status_changed(int line_index, str new_status)
            → emitida cuando el usuario cicla el estado
        navigate_requested(int delta)
            → +1 para siguiente línea, -1 para anterior
    """
    translation_changed = Signal(int, str)
    status_changed      = Signal(int, str)
    navigate_requested  = Signal(int)

    def __init__(self, store: TranslationStore, parent=None):
        super().__init__(parent)
        self.store       = store
        self._unique_id  = None
        self._line_index = -1
        self._all_lines  = []     
        self._blocking   = False  

        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        info_row = QHBoxLayout()
        self._line_info = QLabel("Ninguna línea seleccionada")
        self._line_info.setObjectName("panel_header")
        info_row.addWidget(self._line_info)
        info_row.addStretch()

        self._status_btn = QPushButton(STATUS_LABELS[STATUS_UNTRANSLATED])
        self._status_btn.setFixedWidth(140)
        self._status_btn.clicked.connect(self._on_cycle_status)
        self._status_btn.setToolTip(
            "Clic para cambiar el estado: Sin traducir → Borrador → Revisado"
        )
        info_row.addWidget(self._status_btn)
        layout.addLayout(info_row)

        layout.addWidget(self._section_label("🔍 Contexto de escena"))
        self._context_view = QTextEdit()
        self._context_view.setReadOnly(True)
        self._context_view.setFixedHeight(110)
        self._context_view.setObjectName("context_view")
        layout.addWidget(self._context_view)

        layout.addWidget(self._section_label("📖 Texto Original (Referencia)"))
        self._ref_view = QTextEdit()
        self._ref_view.setReadOnly(True)
        self._ref_view.setObjectName("ref_view")
        layout.addWidget(self._ref_view)

        layout.addWidget(self._section_label("✏️  Traducción"))
        self._translation_edit = QTextEdit()
        self._translation_edit.setObjectName("translation_edit")
        self._translation_edit.setPlaceholderText("Escribe aquí la traducción…")
        self._translation_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._translation_edit)

        nav_row = QHBoxLayout()

        self._prev_btn = QPushButton("← Anterior")
        self._prev_btn.clicked.connect(lambda: self.navigate_requested.emit(-1))
        nav_row.addWidget(self._prev_btn)

        nav_row.addStretch()

        self._char_counter = QLabel("0 caracteres")
        self._char_counter.setObjectName("progress_label")
        nav_row.addWidget(self._char_counter)

        nav_row.addStretch()

        self._next_btn = QPushButton("Siguiente →")
        self._next_btn.clicked.connect(lambda: self.navigate_requested.emit(+1))
        nav_row.addWidget(self._next_btn)

        layout.addLayout(nav_row)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        return lbl

    def _setup_shortcuts(self):
        sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc.activated.connect(self._shortcut_approve_and_next)

        # Alt+→ / Alt+← → navegación
        QShortcut(QKeySequence("Alt+Right"), self).activated.connect(
            lambda: self.navigate_requested.emit(+1)
        )
        QShortcut(QKeySequence("Alt+Left"), self).activated.connect(
            lambda: self.navigate_requested.emit(-1)
        )

    def load_line(self, unique_id: str, line_index: int) -> None:
        self._unique_id  = unique_id
        self._line_index = line_index
        self._all_lines  = self.store.get_lines(unique_id)

        if line_index < 0 or line_index >= len(self._all_lines):
            self._clear()
            return

        line = self._all_lines[line_index]

        self._line_info.setText(
            f"Línea {line_index}  ·  Personaje: {line['name']}  ·  Escena: {line['scene_id']}"
        )

        self._load_context(line_index)
        self._ref_view.setPlainText(line["original_text"])

        self._blocking = True
        self._translation_edit.setPlainText(line["translation"])
        self._blocking = False

        self._refresh_status_button(line["status"])
        self._update_char_counter()

    def clear(self) -> None:
        self._clear()


    def _load_context(self, center: int) -> None:
        translatable_indices = [
            i for i, l in enumerate(self._all_lines) if l["is_translatable"]
        ]
        if center not in translatable_indices:
            self._context_view.clear()
            return

        pos        = translatable_indices.index(center)
        start      = max(0, pos - CONTEXT_WINDOW)
        end        = min(len(translatable_indices) - 1, pos + CONTEXT_WINDOW)
        ctx_lines  = translatable_indices[start:end + 1]

        html_parts = []
        for idx in ctx_lines:
            line = self._all_lines[idx]
            name = line["name"]
            text = line["original_text"].replace("<", "&lt;").replace(">", "&gt;")
            if idx == center:
                html_parts.append(
                    f'<p style="background:#334; padding:2px 4px;">'
                    f'<b style="color:#adf">{name}:</b> {text}</p>'
                )
            else:
                html_parts.append(
                    f'<p style="color:#999; padding:2px 4px;">'
                    f'<b>{name}:</b> {text}</p>'
                )
        self._context_view.setHtml("".join(html_parts))

    def _on_text_changed(self) -> None:
        if self._blocking or self._line_index == -1:
            return
        new_text = self._translation_edit.toPlainText()
        self.translation_changed.emit(self._line_index, new_text)
        self._update_char_counter()

    def _on_cycle_status(self) -> None:
        if self._line_index == -1 or not self._unique_id:
            return
        new_status = self.store.cycle_status(self._unique_id, self._line_index)
        self._refresh_status_button(new_status)
        self.status_changed.emit(self._line_index, new_status)

    def _shortcut_approve_and_next(self) -> None:
        if self._line_index == -1 or not self._unique_id:
            return
        self.store.set_status(self._unique_id, self._line_index, STATUS_REVIEWED)
        self._refresh_status_button(STATUS_REVIEWED)
        self.status_changed.emit(self._line_index, STATUS_REVIEWED)
        self.navigate_requested.emit(+1)

    def _refresh_status_button(self, status: str) -> None:
        self._status_btn.setText(STATUS_LABELS.get(status, status))
        self._status_btn.setStyleSheet(
            STATUS_BUTTON_STYLES.get(status, "")
        )

    def _update_char_counter(self) -> None:
        n = len(self._translation_edit.toPlainText())
        self._char_counter.setText(f"{n} caracteres")

    def _clear(self) -> None:
        self._blocking = True
        self._line_info.setText("Ninguna línea seleccionada")
        self._context_view.clear()
        self._ref_view.clear()
        self._translation_edit.clear()
        self._blocking = False
        self._status_btn.setText(STATUS_LABELS[STATUS_UNTRANSLATED])
        self._status_btn.setStyleSheet(STATUS_BUTTON_STYLES[STATUS_UNTRANSLATED])
        self._char_counter.setText("0 caracteres")


class GlobalSearchDialog(QDialog):
    result_selected = Signal(str, int)

    def __init__(self, store: TranslationStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Búsqueda Global")
        self.resize(700, 450)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        opts_row = QHBoxLayout()
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText("Buscar texto…")
        self._query_edit.returnPressed.connect(self._do_search)
        opts_row.addWidget(self._query_edit)

        self._in_orig = QCheckBox("En original")
        self._in_orig.setChecked(True)
        opts_row.addWidget(self._in_orig)

        self._in_trans = QCheckBox("En traducción")
        self._in_trans.setChecked(True)
        opts_row.addWidget(self._in_trans)

        search_btn = QPushButton("Buscar")
        search_btn.clicked.connect(self._do_search)
        opts_row.addWidget(search_btn)
        layout.addLayout(opts_row)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._results_list)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _do_search(self):
        query = self._query_edit.text().strip()
        if not query:
            return
        results = self.store.search(
            query,
            in_original   = self._in_orig.isChecked(),
            in_translation= self._in_trans.isChecked(),
        )
        self._results_list.clear()
        for r in results:
            line = r["line"]
            label = (
                f"[{r['unique_id'].split('[')[0].strip()}]  "
                f"{line['name']}: {line['original_text'][:60]}…"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (r["unique_id"], r["line_index"]))
            self._results_list.addItem(item)
        self._count_label.setText(f"{len(results)} resultados encontrados")

    def _on_double_click(self, item: QListWidgetItem):
        uid, idx = item.data(Qt.UserRole)
        self.result_selected.emit(uid, idx)
        self.accept()
