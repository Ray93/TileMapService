from tilemapservice.api.wmts_exception import ServiceExceptionReport


def test_service_exception_report_xml():
    report = ServiceExceptionReport(
        code="InvalidParameterValue",
        message="Layer 'unknown' does not exist",
    )
    xml = report.to_xml()

    assert "<?xml version=" in xml
    assert "<ServiceExceptionReport" in xml
    assert 'xmlns="http://www.opengis.net/ows/1.1"' in xml
    assert '<ServiceException code="InvalidParameterValue">' in xml
    assert "Layer 'unknown' does not exist" in xml


def test_service_exception_report_escape():
    report = ServiceExceptionReport(
        code="InvalidParameterValue",
        message="<test>&data</test>",
    )
    xml = report.to_xml()

    assert "&lt;test&gt;&amp;data&lt;/test&gt;" in xml