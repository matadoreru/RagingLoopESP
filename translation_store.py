import json
from copy import deepcopy
from datetime import datetime
from parser_logic import LineData

STATUS_UNTRANSLATED = "untranslated"
STATUS_DRAFT        = "draft"
STATUS_REVIEWED     = "reviewed"

STATUS_CYCLE = [STATUS_UNTRANSLATED, STATUS_DRAFT, STATUS_REVIEWED]
STATUS_LABELS = {
    STATUS_UNTRANSLATED: "Untranslated",
    STATUS_DRAFT:        "Draft",
    STATUS_REVIEWED:     "Reviewed \u2713",
}

class TranslationStore:
    def __init__(self):
        self._asset_lines:   dict[str, list[LineData]] = {}
        self.source_file:    str = ""
        self.session_file:   str = ""

    def set_lines(self, unique_id: str, lines: list[LineData]) -> None:
        if unique_id not in self._asset_lines:
            self._asset_lines[unique_id]  = lines

    def get_lines(self, unique_id: str) -> list[LineData]:
        return self._asset_lines.get(unique_id, [])

    def update_translation(self, unique_id: str, line_index: int, translation: str) -> None:
        lines = self._asset_lines.get(unique_id)
        if lines and line_index < len(lines):
            lines[line_index]["translation"] = translation
            if translation.strip() and lines[line_index]["status"] == STATUS_UNTRANSLATED:
                lines[line_index]["status"] = STATUS_DRAFT

    def set_status(self, unique_id: str, line_index: int, status: str) -> None:
        lines = self._asset_lines.get(unique_id)
        if lines and line_index < len(lines):
            lines[line_index]["status"] = status

    def cycle_status(self, unique_id: str, line_index: int) -> str:
        lines = self._asset_lines.get(unique_id)
        if not lines or line_index >= len(lines):
            return STATUS_UNTRANSLATED
        current = lines[line_index]["status"]
        idx = STATUS_CYCLE.index(current) if current in STATUS_CYCLE else 0
        new_status = STATUS_CYCLE[(idx + 1) % len(STATUS_CYCLE)]
        lines[line_index]["status"] = new_status
        return new_status

    def get_progress(self, unique_id: str) -> dict:
        lines = self._asset_lines.get(unique_id, [])
        translatable = [l for l in lines if l["is_translatable"]]
        total = len(translatable)
        if total == 0:
            return dict(total=0, untranslated=0, draft=0, reviewed=0,
                        pct_translated=0.0, pct_reviewed=0.0)

        reviewed     = sum(1 for l in translatable if l["status"] == STATUS_REVIEWED)
        draft        = sum(1 for l in translatable if l["status"] == STATUS_DRAFT)
        untranslated = total - reviewed - draft

        return dict(
            total         = total,
            untranslated  = untranslated,
            draft         = draft,
            reviewed      = reviewed,
            pct_translated= round((draft + reviewed) / total * 100, 1),
            pct_reviewed  = round(reviewed / total * 100, 1),
        )

    def get_global_progress(self) -> dict:
        totals = dict(total=0, untranslated=0, draft=0, reviewed=0)
        for uid in self._asset_lines:
            p = self.get_progress(uid)
            for k in totals:
                totals[k] += p[k]
        total = totals["total"]
        totals["pct_translated"] = round((totals["draft"] + totals["reviewed"]) / total * 100, 1) if total else 0.0
        totals["pct_reviewed"]   = round(totals["reviewed"] / total * 100, 1) if total else 0.0
        return totals

    def search(self, query: str, in_original: bool = True, in_translation: bool = True) -> list[dict]:
        query_lower = query.lower()
        results = []
        for uid, lines in self._asset_lines.items():
            for idx, line in enumerate(lines):
                if not line["is_translatable"]:
                    continue
                hit = False
                if in_original and query_lower in line["original_text"].lower():
                    hit = True
                if in_translation and query_lower in line["translation"].lower():
                    hit = True
                if hit:
                    results.append({"unique_id": uid, "line_index": idx, "line": line})
        return results

    def save_session(self, json_path: str) -> bool:
        try:
            session = {
                "version":     2,
                "saved_at":    datetime.now().isoformat(),
                "source_file": self.source_file,
                "assets":      {}
            }
            for uid, lines in self._asset_lines.items():
                session["assets"][uid] = [
                    {
                        "idx":         i,
                        "translation": l["translation"],
                        "status":      l["status"],
                    }
                    for i, l in enumerate(lines)
                    if l["is_translatable"]
                ]
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(session, f, ensure_ascii=False, indent=2)
            self.session_file = json_path
            return True
        except Exception:
            return False

    def load_session(self, json_path: str) -> dict:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                session = json.load(f)
            self.session_file = json_path
            self.source_file  = session.get("source_file", "")
            self._apply_session_data(session.get("assets", {}))
            return session
        except Exception:
            return {}

    def _apply_session_data(self, assets_data: dict) -> None:
        for uid, saved_lines in assets_data.items():
            if uid not in self._asset_lines:
                continue
            lines = self._asset_lines[uid]
            for entry in saved_lines:
                idx = entry["idx"]
                if idx < len(lines):
                    lines[idx]["translation"] = entry.get("translation", "")
                    lines[idx]["status"]      = entry.get("status", STATUS_UNTRANSLATED)

    @property
    def loaded_asset_ids(self) -> list[str]:
        return list(self._asset_lines.keys())