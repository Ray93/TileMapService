from tilemapservice.readers.cdi_parser import CdiParser


def test_cdi_parser_reads_envelope_bounds(tmp_path):
    cdi = tmp_path / "conf.cdi"
    cdi.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<EnvelopeN xmlns="http://www.esri.com/schemas/ArcGIS/10.0">
  <XMin>37.1</XMin>
  <YMin>55.4</YMin>
  <XMax>37.9</XMax>
  <YMax>56.0</YMax>
</EnvelopeN>
""",
        encoding="utf-8",
    )
    assert CdiParser(cdi).get_bounds() == (37.1, 55.4, 37.9, 56.0)

