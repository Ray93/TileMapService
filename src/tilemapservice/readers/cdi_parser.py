"""ArcGIS conf.cdi parser."""
from pathlib import Path
import xml.etree.ElementTree as ET


class CdiParser:
    """Parse CDI envelope bounds."""

    def __init__(self, cdi_path: str | Path):
        self.cdi_path = Path(cdi_path)
        self.tree = ET.parse(self.cdi_path)
        self.root = self.tree.getroot()

    def _float(self, name: str) -> float:
        elem = self.root.find(f".//{{*}}{name}")
        if elem is None or elem.text is None:
            raise ValueError(f"conf.cdi missing {name}")
        return float(elem.text.strip())

    def get_bounds(self) -> tuple[float, float, float, float]:
        return self._float("XMin"), self._float("YMin"), self._float("XMax"), self._float("YMax")

