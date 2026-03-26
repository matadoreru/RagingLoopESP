import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter,
    QToolBar, QMessageBox, QFileDialog, QStatusBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui  import QAction, QKeySequence

from parser_logic      import AssetsParser
from translation_store import TranslationStore
from ui_asset_browser  import AssetBrowserPanel, LinesBrowserPanel
from ui_editor         import EditorPanel, GlobalSearchDialog

class TranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Raging Loop - Translation Tool")
        self.resize(1400, 860)

        self._parser = AssetsParser()
        self._store  = TranslationStore()

        self._current_asset_id   = None
        self._current_line_index = -1

        self._build_ui()
        self._connect_signals()
        self._update_status("Ready. Open a resources.assets file to begin.")

    def _build_ui(self):
        self._build_toolbar()

        splitter = QSplitter(Qt.Horizontal)

        self._asset_browser = AssetBrowserPanel(self._store)
        self._lines_browser = LinesBrowserPanel(self._store)
        self._editor        = EditorPanel(self._store)

        splitter.addWidget(self._asset_browser)
        splitter.addWidget(self._lines_browser)
        splitter.addWidget(self._editor)
        splitter.setSizes([260, 380, 760])

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._add_action(tb, "Open .assets",   self._action_open_assets,
                         "Open the game's resources.assets file")
        self._add_action(tb, "Save .assets",   self._action_save_assets,
                         "Compile and save the modified .assets file")
        tb.addSeparator()

        self._add_action(tb, "Save Session",  self._action_save_session,
                         "Save translation progress to a JSON file")
        self._add_action(tb, "Load Session",   self._action_load_session,
                         "Load a saved translation session (.json)")
        tb.addSeparator()

        self._add_action(tb, "Global Search",  self._action_global_search,
                         "Search text in all assets [Ctrl+F]",
                         shortcut="Ctrl+F")

    def _add_action(self, toolbar, label, slot, tooltip="", shortcut=""):
        act = QAction(label, self)
        act.setToolTip(tooltip)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        toolbar.addAction(act)
        return act

    def _connect_signals(self):
        self._asset_browser.asset_selected.connect(self._on_asset_selected)
        self._lines_browser.line_selected.connect(self._on_line_selected)
        self._editor.translation_changed.connect(self._on_translation_changed)
        self._editor.status_changed.connect(self._on_status_changed)
        self._editor.navigate_requested.connect(self._on_navigate)

    def _action_open_assets(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select resources.assets", "",
            "Assets Files (*.assets *.bundle);;All Files (*)"
        )
        if not path:
            return

        self._update_status("Loading file...")
        unique_ids = self._parser.load_assets_file(path)

        if not unique_ids:
            QMessageBox.critical(self, "Error",
                "Could not read the file. It might be corrupted or in use.")
            self._update_status("Error loading file.")
            return

        self._store.source_file = path

        for uid in unique_ids:
            lines = self._parser.parse_script(uid)
            self._store.set_lines(uid, lines)

        self._asset_browser.populate(unique_ids)
        self.setWindowTitle(f"Raging Loop - {os.path.basename(path)}")
        self._update_status(
            f"Loaded {len(unique_ids)} TextAssets from {os.path.basename(path)}"
        )

    def _action_save_assets(self):
        if not self._parser.is_loaded:
            QMessageBox.warning(self, "No file", "Open an .assets file first.")
            return

        for uid in self._store.loaded_asset_ids:
            self._parser.apply_lines_to_asset(uid, self._store.get_lines(uid))

        path, _ = QFileDialog.getSaveFileName(
            self, "Save .assets file",
            "translated_resources.assets",
            "Assets Files (*.assets)"
        )
        if not path:
            return

        ok = self._parser.save_bundle(path)
        if ok:
            QMessageBox.information(self, "Saved",
                f"File saved at:\n{path}\n\nReplace the original in the game folder.")
            self._update_status(f"Assets saved to {os.path.basename(path)}")
        else:
            QMessageBox.critical(self, "Error", "Could not save the file.")

    def _action_save_session(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", "translation_session.json", "JSON (*.json)"
        )
        if path:
            ok = self._store.save_session(path)
            self._update_status(
                f"Session saved to {os.path.basename(path)}" if ok
                else "Error saving session."
            )

    def _action_load_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Session", "", "JSON (*.json)"
        )
        if not path:
            return
        session = self._store.load_session(path)
        if not session:
            QMessageBox.critical(self, "Error", "Could not load the session.")
            return

        if not self._parser.is_loaded and self._store.source_file:
            reply = QMessageBox.question(
                self, "Load original file",
                f"Open the original .assets file too?\n{self._store.source_file}",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                ids = self._parser.load_assets_file(self._store.source_file)
                for uid in ids:
                    self._store.set_lines(uid, self._parser.parse_script(uid))
                self._store._apply_session_data(
                    {uid: [
                        {"idx": i, "translation": l["translation"], "status": l["status"]}
                        for i, l in enumerate(self._store.get_lines(uid))
                        if l["is_translatable"]
                    ] for uid in ids}
                )
                self._asset_browser.populate(ids)

        self._asset_browser.refresh_progress()
        if self._current_asset_id:
            self._lines_browser.populate(self._current_asset_id)
        self._update_status(f"Session loaded: {os.path.basename(path)}")

    def _action_global_search(self):
        dlg = GlobalSearchDialog(self._store, self)
        dlg.result_selected.connect(self._jump_to)
        dlg.exec()

    def _on_asset_selected(self, unique_id: str):
        self._current_asset_id   = unique_id
        self._current_line_index = -1
        self._lines_browser.populate(unique_id)
        self._editor.clear()
        self._update_status(f"Asset: {unique_id}")

    def _on_line_selected(self, line_index: int):
        self._current_line_index = line_index
        self._editor.load_line(self._current_asset_id, line_index)

    def _on_translation_changed(self, line_index: int, new_text: str):
        self._store.update_translation(self._current_asset_id, line_index, new_text)
        self._lines_browser.refresh_item(line_index)
        self._asset_browser.refresh_progress()

    def _on_status_changed(self, line_index: int, new_status: str):
        self._lines_browser.refresh_item(line_index)
        self._asset_browser.refresh_progress()

    def _on_navigate(self, delta: int):
        lines_list       = self._lines_browser._lines_list
        current_item_row = lines_list.currentRow()
        target_row       = current_item_row + delta
        if 0 <= target_row < lines_list.count():
            lines_list.setCurrentRow(target_row)

    def _jump_to(self, unique_id: str, line_index: int):
        if unique_id != self._current_asset_id:
            self._asset_browser.select_asset(unique_id)
            QTimer.singleShot(50, lambda: self._lines_browser.select_line(line_index))
        else:
            self._lines_browser.select_line(line_index)

    def _update_status(self, msg: str):
        self.statusBar().showMessage(msg)

def main():
    app = QApplication(sys.argv)
    window = TranslatorApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()