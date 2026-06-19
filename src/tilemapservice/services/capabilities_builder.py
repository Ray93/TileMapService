"""WMTS GetCapabilities XML document builder."""
from typing import Optional

from tilemapservice.models.source import DataSource
from tilemapservice.utils.coordinates import (
    create_webmercator_matrix_set,
    create_geographic_matrix_set,
    WEBMERCATOR_SCALE_DENOMINATORS,
    GEOGRAPHIC_SCALE_DENOMINATORS,
)


class CapabilitiesBuilder:
    """Generates WMTS GetCapabilities XML document."""

    def __init__(
        self,
        sources: list[DataSource],
        service_url: str,
        title: str = "TileMapService",
    ):
        self.sources = sources
        self.service_url = service_url.rstrip("/")
        self.title = title
        self._cached_xml: Optional[str] = None

    def generate(self) -> str:
        """Generate complete WMTS GetCapabilities XML."""
        if self._cached_xml:
            return self._cached_xml

        xml_parts = [
            self._xml_header(),
            self._service_identification(),
            self._operations_metadata(),
            self._contents(),
            self._tile_matrix_sets(),
            self._xml_footer(),
        ]
        self._cached_xml = "\n".join(xml_parts)
        return self._cached_xml

    def regenerate(self) -> str:
        """Force regenerate XML (call when sources change)."""
        self._cached_xml = None
        return self.generate()

    def _xml_header(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0"
              xmlns:ows="http://www.opengis.net/ows/1.1"
              xmlns:xlink="http://www.w3.org/1999/xlink"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xsi:schemaLocation="http://www.opengis.net/wmts/1.0 http://schemas.opengis.net/wmts/1.0/wmtsGetCapabilities_response.xsd"
              version="1.0.0">"""

    def _service_identification(self) -> str:
        return f"""
  <ows:ServiceIdentification>
    <ows:Title>{self._escape_xml(self.title)}</ows:Title>
    <ows:ServiceType>OGC WMTS</ows:ServiceType>
    <ows:ServiceTypeVersion>1.0.0</ows:ServiceTypeVersion>
  </ows:ServiceIdentification>"""

    def _operations_metadata(self) -> str:
        return f"""
  <ows:OperationsMetadata>
    <ows:Operation name="GetCapabilities">
      <ows:DCP>
        <ows:HTTP>
          <ows:Get xlink:href="{self.service_url}/wmts?"/>
        </ows:HTTP>
      </ows:DCP>
    </ows:Operation>
    <ows:Operation name="GetTile">
      <ows:DCP>
        <ows:HTTP>
          <ows:Get xlink:href="{self.service_url}/wmts?"/>
        </ows:HTTP>
      </ows:DCP>
    </ows:Operation>
  </ows:OperationsMetadata>"""

    def _contents(self) -> str:
        layers_xml = []
        for source in self.sources:
            layers_xml.append(self._layer_xml(source))
        return "\n  <Contents>\n" + "\n".join(layers_xml) + "\n  </Contents>"

    def _layer_xml(self, source: DataSource) -> str:
        available_tms = self._get_available_tilematrixsets(source)
        tms_links = []
        for tms_id, limits in available_tms.items():
            tms_links.append(self._tilematrixset_link_xml(tms_id, limits))

        return f"""    <Layer>
      <ows:Title>{self._escape_xml(source.name)}</ows:Title>
      <ows:Abstract>{self._escape_xml(source.description or "")}</ows:Abstract>
      <ows:Identifier>{self._escape_xml(source.name)}</ows:Identifier>
      <Style isDefault="true">
        <ows:Identifier>default</ows:Identifier>
      </Style>
      <Format>image/png</Format>
      <Format>image/jpeg</Format>
{"".join(tms_links)}
    </Layer>"""

    def _tilematrixset_link_xml(self, tms_id: str, limits: list[dict]) -> str:
        limits_xml = []
        for limit in limits:
            limits_xml.append(f"""        <TileMatrixLimits>
          <TileMatrix>{limit["matrix"]}</TileMatrix>
          <MinTileRow>{limit["min_row"]}</MinTileRow>
          <MaxTileRow>{limit["max_row"]}</MaxTileRow>
          <MinTileCol>{limit["min_col"]}</MinTileCol>
          <MaxTileCol>{limit["max_col"]}</MaxTileCol>
        </TileMatrixLimits>""")

        limits_block = "\n        <TileMatrixSetLimits>\n" + "\n".join(limits_xml) + "\n        </TileMatrixSetLimits>\n" if limits_xml else ""

        return f"""      <TileMatrixSetLink>
        <TileMatrixSet>{self._escape_xml(tms_id)}</TileMatrixSet>
{limits_block}      </TileMatrixSetLink>"""

    def _get_available_tilematrixsets(self, source: DataSource) -> dict[str, list[dict]]:
        """Get available TileMatrixSets for a source with limits."""
        result = {}
        source_crs = f"EPSG:{source.spatial_ref_wkid}"

        # WebMercator available for EPSG:3857 sources
        if source.spatial_ref_wkid == 3857:
            result["WebMercator"] = self._calculate_limits(source, "WebMercator")
            result["WebMercator-native"] = []

        # Geographic available for EPSG:4326 sources
        if source.spatial_ref_wkid == 4326:
            result["Geographic"] = self._calculate_limits(source, "Geographic")
            result["Geographic-native"] = []

        # Native matrix for any CRS
        native_id = f"EPSG:{source.spatial_ref_wkid}-native"
        result[native_id] = []

        # Also add plain EPSG:XXX for non-standard CRS
        if source.spatial_ref_wkid not in (3857, 4326):
            result[f"EPSG:{source.spatial_ref_wkid}"] = self._calculate_limits(source, f"EPSG:{source.spatial_ref_wkid}")

        return result

    def _calculate_limits(self, source: DataSource, tms_id: str) -> list[dict]:
        """Calculate TileMatrixSetLimits for each zoom level."""
        # Simplified: return empty limits for now (full calculation would transform bounds)
        # For now, just indicate valid zoom range
        limits = []
        for z in range(source.min_zoom, source.max_zoom + 1):
            limits.append({
                "matrix": str(z),
                "min_row": 0,
                "max_row": (1 << z) - 1 if "Mercator" in tms_id else (1 << z) - 1,
                "min_col": 0,
                "max_col": (1 << z) - 1 if "Mercator" in tms_id else (1 << (z + 1)) - 1,
            })
        return limits

    def _tile_matrix_sets(self) -> str:
        """Generate TileMatrixSet definitions."""
        tms_xml = []

        # WebMercator
        tms_xml.append(self._webmercator_tms_xml())

        # Geographic
        tms_xml.append(self._geographic_tms_xml())

        # Native matrices for each source
        for source in self.sources:
            tms_xml.append(self._native_tms_xml(source))

        return "\n".join(tms_xml)

    def _webmercator_tms_xml(self) -> str:
        matrices = []
        for z in range(19):
            scale = WEBMERCATOR_SCALE_DENOMINATORS[z]
            size = 1 << z
            matrices.append(f"""    <TileMatrix>
      <ows:Identifier>{z}</ows:Identifier>
      <ScaleDenominator>{scale:.7f}</ScaleDenominator>
      <TopLeftCorner>-20037508.342787 20037508.342787</TopLeftCorner>
      <TileWidth>256</TileWidth>
      <TileHeight>256</TileHeight>
      <MatrixWidth>{size}</MatrixWidth>
      <MatrixHeight>{size}</MatrixHeight>
    </TileMatrix>""")

        return f"""  <TileMatrixSet>
    <ows:Identifier>WebMercator</ows:Identifier>
    <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
{"".join(matrices)}
  </TileMatrixSet>"""

    def _geographic_tms_xml(self) -> str:
        matrices = []
        for z in range(19):
            scale = GEOGRAPHIC_SCALE_DENOMINATORS[z]
            width = 2 << z  # 2 * 2^z
            height = 1 << z  # 1 * 2^z
            matrices.append(f"""    <TileMatrix>
      <ows:Identifier>{z}</ows:Identifier>
      <ScaleDenominator>{scale:.7f}</ScaleDenominator>
      <TopLeftCorner>-180 90</TopLeftCorner>
      <TileWidth>256</TileWidth>
      <TileHeight>256</TileHeight>
      <MatrixWidth>{width}</MatrixWidth>
      <MatrixHeight>{height}</MatrixHeight>
    </TileMatrix>""")

        return f"""  <TileMatrixSet>
    <ows:Identifier>Geographic</ows:Identifier>
    <ows:SupportedCRS>urn:ogc:def:crs:EPSG::4326</ows:SupportedCRS>
{"".join(matrices)}
  </TileMatrixSet>"""

    def _native_tms_xml(self, source: DataSource) -> str:
        """Generate native TileMatrixSet for a source."""
        if not source.tile_matrix_set:
            return ""

        tms = source.tile_matrix_set
        epsg = source.spatial_ref_wkid
        native_id = f"EPSG:{epsg}-native"

        matrices = []
        resolutions = tms.resolutions or {}
        for z in sorted(resolutions.keys()):
            res = resolutions[z]
            # Calculate matrix size from resolution
            if tms.crs == "EPSG:3857":
                world_size = 40075016.68557849
                matrix_width = int(round(world_size / (res * tms.tile_width)))
                matrix_height = matrix_width
            elif tms.crs == "EPSG:4326":
                matrix_width = int(round(360 / (res * tms.tile_width)))
                matrix_height = int(round(180 / (res * tms.tile_height)))
            else:
                matrix_width = 1 << z  # fallback
                matrix_height = matrix_width

            # Scale denominator: resolution * 0.28mm / pixel
            scale = res * 4000 / 0.28  # approximate

            matrices.append(f"""    <TileMatrix>
      <ows:Identifier>{z}</ows:Identifier>
      <ScaleDenominator>{scale:.4f}</ScaleDenominator>
      <TopLeftCorner>{tms.origin_x} {tms.origin_y}</TopLeftCorner>
      <TileWidth>{tms.tile_width}</TileWidth>
      <TileHeight>{tms.tile_height}</TileHeight>
      <MatrixWidth>{matrix_width}</MatrixWidth>
      <MatrixHeight>{matrix_height}</MatrixHeight>
    </TileMatrix>""")

        if not matrices:
            return ""

        return f"""  <TileMatrixSet>
    <ows:Identifier>{native_id}</ows:Identifier>
    <ows:SupportedCRS>urn:ogc:def:crs:EPSG::{epsg}</ows:SupportedCRS>
{"".join(matrices)}
  </TileMatrixSet>"""

    def _xml_footer(self) -> str:
        return "</Capabilities>"

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
