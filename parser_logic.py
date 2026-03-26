import re
import UnityPy

LINE_TYPE_SYSTEM    = "system"     
LINE_TYPE_DIALOGUE  = "dialogue"   
LINE_TYPE_CHOICE    = "choice"     

class LineData(dict):
    DEFAULTS = {
        "original_raw":   "",
        "is_translatable": False,
        "type":           LINE_TYPE_SYSTEM,
        "original_text":  "",
        "translation":    "",
        "status":         "untranslated",
        "name":           "Narrator",
        "scene_id":       "N/A",
        "parts":          [],
    }

    def __init__(self, **kwargs):
        super().__init__({**self.DEFAULTS, **kwargs})

class AssetsParser:
    def __init__(self):
        self._env = None
        self._text_assets: dict = {}

    def load_assets_file(self, file_path: str) -> list[str]:
        try:
            self._env = UnityPy.load(file_path)
            self._text_assets = {}

            if not self._env.objects:
                print(f"[Parser] No objects found in: {file_path}")
                return []

            for obj in self._env.objects:
                if obj.type.name == "TextAsset":
                    data = obj.read()
                    unique_id = f"{data.m_Name} [ID: {obj.path_id}]"
                    self._text_assets[unique_id] = obj

            return sorted(self._text_assets.keys())

        except Exception as exc:
            print(f"[Parser] Critical error loading assets: {exc}")
            return []

    def parse_script(self, unique_id: str) -> list[LineData]:
        if unique_id not in self._text_assets:
            return []

        obj  = self._text_assets[unique_id]
        data = obj.read()

        raw_text = data.m_Script
        if isinstance(raw_text, bytes):
            raw_text = raw_text.decode("utf-8", errors="ignore")

        return self._parse_script_text(raw_text)

    @staticmethod
    def _parse_script_text(full_text: str) -> list[LineData]:
        raw_lines       = full_text.split("\r\n")
        result          = []
        current_name    = "Narrator"
        current_id      = "N/A"
        inside_message  = False

        for raw in raw_lines:
            line = LineData(original_raw=raw, name=current_name, scene_id=current_id)

            if raw.startswith("#MesName"):
                m = re.search(r'#MesName\((.*)\)', raw)
                current_name = m.group(1) if (m and m.group(1)) else "Narrator"
                line["name"] = current_name

            elif raw.startswith("#MesSta"):
                m = re.search(r'#MesSta\(([^,]*),', raw)
                if m:
                    current_id = m.group(1)
                line["scene_id"] = current_id
                inside_message   = True

            elif raw.startswith("#MesEnd"):
                inside_message = False

            elif inside_message and raw and not raw.startswith("#"):
                line.update({
                    "is_translatable": True,
                    "type":            LINE_TYPE_DIALOGUE,
                    "original_text":   raw,
                })

            elif raw.startswith("#SelectLimited"):
                parts = raw.split(",")
                line.update({
                    "is_translatable": True,
                    "type":            LINE_TYPE_CHOICE,
                    "original_text":   raw,
                    "parts":           parts,
                })

            result.append(line)

        return result

    def apply_lines_to_asset(self, unique_id: str, lines: list[LineData]) -> None:
        if unique_id not in self._text_assets:
            return

        rebuilt = []
        for line in lines:
            if line["is_translatable"] and line["type"] == LINE_TYPE_DIALOGUE:
                rebuilt.append(
                    line["translation"] if line["translation"].strip() else line["original_text"]
                )
            elif line["is_translatable"] and line["type"] == LINE_TYPE_CHOICE:
                if line["translation"].strip():
                    parts = list(line["parts"])           
                    parts[1] = line["translation"]
                    rebuilt.append(",".join(parts))
                else:
                    rebuilt.append(line["original_raw"])
            else:
                rebuilt.append(line["original_raw"])

        obj  = self._text_assets[unique_id]
        data = obj.read()
        data.m_Script = "\r\n".join(rebuilt)
        data.save()

    def save_bundle(self, output_path: str) -> bool:
        if self._env is None:
            print("[Parser] No bundle loaded.")
            return False
        try:
            with open(output_path, "wb") as f:
                f.write(self._env.file.save())
            print(f"[Parser] Bundle saved at: {output_path}")
            return True
        except Exception as exc:
            print(f"[Parser] Error saving bundle: {exc}")
            return False

    @property
    def is_loaded(self) -> bool:
        return self._env is not None

    @property
    def asset_ids(self) -> list[str]:
        return sorted(self._text_assets.keys())