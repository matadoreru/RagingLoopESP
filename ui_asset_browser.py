from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QComboBox, QLineEdit, QProgressBar, QFrame
)
from PySide6.QtCore  import Qt, Signal, QTimer
from PySide6.QtGui   import QColor, QIcon

from translation_store import (
    TranslationStore,
    STATUS_UNTRANSLATED, STATUS_DRAFT, STATUS_REVIEWED, STATUS_LABELS
)

STATUS_COLORS = {
    STATUS_UNTRANSLATED: QColor("#E57373"),
    STATUS_DRAFT:        QColor("#FFB74D"),
    STATUS_REVIEWED:     QColor("#81C784"),
}

class AssetBrowserPanel(QWidget):
    asset_selected = Signal(str)

    def __init__(self, store: TranslationStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("Text Assets")
        header.setObjectName("panel_header")
        layout.addWidget(header)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Filter assets...")
        self._search_box.textChanged.connect(self._filter_assets)
        layout.addWidget(self._search_box)

        self._asset_list = QListWidget()
        self._asset_list.currentRowChanged.connect(self._on_asset_selected)
        layout.addWidget(self._asset_list)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._global_label = QLabel("Global Progress: -")
        self._global_label.setObjectName("progress_label")
        layout.addWidget(self._global_label)

        self._global_bar = QProgressBar()
        self._global_bar.setRange(0, 100)
        self._global_bar.setTextVisible(True)
        layout.addWidget(self._global_bar)

    def populate(self, unique_ids: list[str]) -> None:
        self._all_ids = unique_ids
        self._asset_list.clear()
        for uid in unique_ids:
            self._asset_list.addItem(self._make_item(uid))
        self.refresh_progress()

    def refresh_progress(self) -> None:
        for i in range(self._asset_list.count()):
            item = self._asset_list.item(i)
            uid  = item.data(Qt.UserRole)
            p    = self.store.get_progress(uid)
            pct  = p["pct_translated"]
            tooltip = (
                f"{uid}\nTotal: {p['total']} | Untranslated: {p['untranslated']} | "
                f"Draft: {p['draft']} | Reviewed: {p['reviewed']}\n"
                f"Translated: {pct}% | Reviewed: {p['pct_reviewed']}%"
            )
            item.setToolTip(tooltip)
            if pct == 0:
                item.setForeground(QColor("#aaaaaa"))
            elif pct < 100:
                item.setForeground(QColor("#FFB74D"))
            else:
                item.setForeground(QColor("#81C784"))

        gp = self.store.get_global_progress()
        self._global_label.setText(
            f"Global: {gp['pct_translated']}% translated | {gp['pct_reviewed']}% reviewed"
        )
        self._global_bar.setValue(int(gp["pct_translated"]))

    def select_asset(self, unique_id: str) -> None:
        for i in range(self._asset_list.count()):
            if self._asset_list.item(i).data(Qt.UserRole) == unique_id:
                self._asset_list.setCurrentRow(i)
                return

    def current_asset_id(self) -> str | None:
        item = self._asset_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _make_item(self, uid: str) -> QListWidgetItem:
        item = QListWidgetItem(uid)
        item.setData(Qt.UserRole, uid)
        return item

    def _on_asset_selected(self, row: int) -> None:
        if row < 0:
            return
        uid = self._asset_list.item(row).data(Qt.UserRole)
        self.asset_selected.emit(uid)

    def _filter_assets(self, text: str) -> None:
        query = text.lower()
        for i in range(self._asset_list.count()):
            item = self._asset_list.item(i)
            item.setHidden(query not in item.text().lower())

class LinesBrowserPanel(QWidget):
    line_selected = Signal(int)

    def __init__(self, store: TranslationStore, parent=None):
        super().__init__(parent)
        self.store      = store
        self._unique_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("Script Lines")
        header.setObjectName("panel_header")
        layout.addWidget(header)

        filter_row = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search lines...")
        self._search_box.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self._search_box)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Untranslated", "Draft", "Reviewed"])
        self._filter_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._filter_combo)
        layout.addLayout(filter_row)

        self._asset_bar = QProgressBar()
        self._asset_bar.setRange(0, 100)
        self._asset_bar.setFormat("%v% translated")
        self._asset_bar.setFixedHeight(14)
        layout.addWidget(self._asset_bar)

        self._lines_list = QListWidget()
        self._lines_list.currentRowChanged.connect(self._on_line_selected)
        layout.addWidget(self._lines_list)

        self._counter_label = QLabel("0 lines")
        self._counter_label.setObjectName("progress_label")
        layout.addWidget(self._counter_label)

    def populate(self, unique_id: str) -> None:
        self._unique_id = unique_id
        self._refresh_list()
        self._update_progress_bar()

    def refresh_item(self, line_index: int) -> None:
        for i in range(self._lines_list.count()):
            item = self._lines_list.item(i)
            if item.data(Qt.UserRole) == line_index:
                self._update_item_appearance(item, line_index)
                break
        self._update_progress_bar()

    def select_line(self, line_index: int) -> None:
        for i in range(self._lines_list.count()):
            if self._lines_list.item(i).data(Qt.UserRole) == line_index:
                self._lines_list.setCurrentRow(i)
                return

    def current_line_index(self) -> int:
        item = self._lines_list.currentItem()
        return item.data(Qt.UserRole) if item else -1

    def _refresh_list(self) -> None:
        self._lines_list.blockSignals(True)
        self._lines_list.clear()
        lines = self.store.get_lines(self._unique_id) if self._unique_id else []
        for i, line in enumerate(lines):
            if not line["is_translatable"]:
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, i)
            self._update_item_appearance(item, i)
            self._lines_list.addItem(item)
        self._lines_list.blockSignals(False)
        self._apply_filters()

    def _update_item_appearance(self, item: QListWidgetItem, line_index: int) -> None:
            if not self._unique_id: 
                return
                
            lines = self.store.get_lines(self._unique_id)
            if line_index >= len(lines): 
                return
                
            line = lines[line_index]
            status = line["status"]
            name = line["name"]
            label = STATUS_LABELS.get(status, status)
            
            clean_text = line["original_text"].replace("\n", " ")
            
            if len(clean_text) > 45:
                preview = clean_text[:45] + "..."
            else:
                preview = clean_text
                
            item.setText(f"[{label}] {name}: {preview}")
            item.setForeground(STATUS_COLORS.get(status, QColor("#ffffff")))
            item.setToolTip(line["original_text"])

    def _apply_filters(self) -> None:
        query      = self._search_box.text().lower()
        filter_idx = self._filter_combo.currentIndex()
        status_map = {1: STATUS_UNTRANSLATED, 2: STATUS_DRAFT, 3: STATUS_REVIEWED}
        target_status = status_map.get(filter_idx)
        lines   = self.store.get_lines(self._unique_id) if self._unique_id else []
        visible = 0
        for i in range(self._lines_list.count()):
            item       = self._lines_list.item(i)
            line_index = item.data(Qt.UserRole)
            if line_index >= len(lines):
                item.setHidden(True)
                continue
            line   = lines[line_index]
            hidden = False
            if target_status and line["status"] != target_status:
                hidden = True
            if query and query not in line["original_text"].lower() and query not in line["translation"].lower() and query not in line["name"].lower():
                hidden = True
            item.setHidden(hidden)
            if not hidden: visible += 1
        self._counter_label.setText(f"{visible} lines visible")

    def _update_progress_bar(self) -> None:
        if not self._unique_id: return
        p = self.store.get_progress(self._unique_id)
        self._asset_bar.setValue(int(p["pct_translated"]))
        self._asset_bar.setFormat(f"{p['pct_translated']}% translated | {p['pct_reviewed']}% reviewed ({p['reviewed']}/{p['total']})")

    def _on_line_selected(self, row: int) -> None:
        if row < 0: return
        line_index = self._lines_list.item(row).data(Qt.UserRole)
        self.line_selected.emit(line_index)