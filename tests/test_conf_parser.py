from tilemapservice.readers.conf_parser import ConfParser


def test_conf_parser_reads_spatial_reference_origin_tile_info_and_levels(tmp_path):
    conf = tmp_path / "Conf.xml"
    conf.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<CacheInfo xmlns="http://www.esri.com/schemas/ArcGIS/10.0">
  <TileCacheInfo>
    <SpatialReference><WKID>4326</WKID><LatestWKID>4326</LatestWKID></SpatialReference>
    <TileOrigin><X>-180</X><Y>90</Y></TileOrigin>
    <TileCols>256</TileCols>
    <TileRows>256</TileRows>
    <DPI>96</DPI>
    <LODInfos>
      <LODInfo><LevelID>16</LevelID><Scale>4508.94</Scale><Resolution>0.0000107288</Resolution></LODInfo>
      <LODInfo><LevelID>17</LevelID><Scale>2254.47</Scale><Resolution>0.0000053644</Resolution></LODInfo>
    </LODInfos>
  </TileCacheInfo>
</CacheInfo>
""",
        encoding="utf-8",
    )
    parser = ConfParser(conf)
    assert parser.get_spatial_reference()["wkid"] == 4326
    assert parser.get_tile_origin() == {"x": -180.0, "y": 90.0}
    assert parser.get_tile_info()["tile_cols"] == 256
    assert parser.get_levels()[1]["level"] == 17

