"""WMTS OWS ServiceException response builder."""


class ServiceExceptionReport:
    """OWS 1.1 ServiceExceptionReport for WMTS errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def to_xml(self) -> str:
        """Generate ServiceExceptionReport XML."""
        escaped_message = self._escape_xml(self.message)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ServiceExceptionReport xmlns="http://www.opengis.net/ows/1.1"
                        version="1.1.0">
  <ServiceException code="{self.code}">{escaped_message}</ServiceException>
</ServiceExceptionReport>"""

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")