"""ArcGIS Conf.xml parser."""
from pathlib import Path
import xml.etree.ElementTree as ET


class ConfParser:
    """Parse spatial reference, tile origin, tile info, and LOD levels."""

    def __init__(self, conf_path: str | Path):
        self.conf_path = Path(conf_path)
        self.tree = ET.parse(self.conf_path)
        self.root = self.tree.getroot()

    def _find(self, name: str):
        return self.root.find(f".//{{*}}{name}")

    def _text(self, name: str, default: str | None = None) -> str:
        elem = self._find(name)
        if elem is None or elem.text is None:
            if default is None:
                raise ValueError(f"Conf.xml missing {name}")
            return default
        return elem.text.strip()

    def get_spatial_reference(self) -> dict:
        wkid = int(self._text("WKID", "3857"))
        latest = self._find("LatestWKID")
        return {
            "wkid": wkid,
            "latest_wkid": int(latest.text.strip()) if latest is not None and latest.text else wkid,
        }

    def get_tile_origin(self) -> dict:
        origin = self._find("TileOrigin")
        if origin is None:
            return {"x": -20037508.342787, "y": 20037508.342787}
        x = origin.find(".//{*}X")
        y = origin.find(".//{*}Y")
        return {
            "x": float(x.text.strip()) if x is not None and x.text else -20037508.342787,
            "y": float(y.text.strip()) if y is not None and y.text else 20037508.342787,
        }

    def get_tile_info(self) -> dict:
        return {
            "tile_cols": int(self._text("TileCols", "256")),
            "tile_rows": int(self._text("TileRows", "256")),
            "dpi": int(float(self._text("DPI", "96"))),
        }

    def get_levels(self) -> list[dict]:
        levels = []
        for lod in self.root.findall(".//{*}LODInfo"):
            level = lod.find(".//{*}LevelID")
            scale = lod.find(".//{*}Scale")
            resolution = lod.find(".//{*}Resolution")
            if level is None or level.text is None:
                continue
            levels.append(
                {
                    "level": int(level.text.strip()),
                    "scale": float(scale.text.strip()) if scale is not None and scale.text else 0.0,
                    "resolution": float(resolution.text.strip()) if resolution is not None and resolution.text else 0.0,
                }
            )
        return levels

