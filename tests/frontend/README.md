# Frontend Unit Tests

Browser-based unit tests for TileMapService frontend JavaScript code.

## Overview

These tests use [QUnit](https://qunitjs.com/) loaded from CDN and test frontend code in isolation. No build chain or bundler is required—just open the HTML files in a browser.

## Test Files

### `test_crs_utils.html`

Tests for the `buildLeafletCrs()` function used in the map preview interface.

**Coverage:**
- Valid L.Proj.CRS construction for EPSG:4490 (CGCS2000)
- Valid L.Proj.CRS construction for EPSG:3857 (Web Mercator)
- Returns `null` when `proj4` string is missing
- Returns `null` when `tile_matrix` is missing
- Verifies proj4 and proj4leaflet libraries are loaded
- Custom resolutions array handling
- Custom origin values
- proj4 definition registration

## Running Tests

### Option 1: Local HTTP Server (Recommended)

Serve from the project root to ensure correct library paths:

```bash
# From project root directory
cd /path/to/tilemapservice2
python -m http.server 8080

# Node.js alternative
npx http-server -p 8080

# PHP alternative
php -S localhost:8080
```

Then open: `http://localhost:8080/tests/frontend/test_crs_utils.html`

### Option 2: Direct File Open

You can try opening the test HTML file directly in your browser:

```
file:///path/to/tilemapservice2/tests/frontend/test_crs_utils.html
```

This works in most browsers, but some may block loading local JavaScript files due to CORS policies.

### Option 3: Via TileMapService

If the service is running with static file serving configured:

1. Start the service:
   ```bash
   uv run python src/main.py --port 8000
   ```

2. Access tests at:
   ```
   http://localhost:8000/tests/frontend/test_crs_utils.html
   ```
   (Note: This requires configuring static file serving for the `/tests` path)

## Interpreting Results

### Passing Tests
- All tests green ✓
- Total: 9 tests
- No failures or errors

### Common Failure Scenarios

**Library Load Failures:**
- Check that `../../src/static/libs/` paths are correct
- Verify Leaflet, proj4js, and proj4leaflet are vendored

**CRS Construction Failures:**
- Indicates a breaking change in `buildLeafletCrs()` function
- Review function signature and return values

## Dependencies

Tests load these vendored libraries from `src/static/libs/`:
- `leaflet/leaflet.js` - Leaflet 1.9.4
- `proj4js/proj4.js` - proj4js 2.9.0
- `proj4leaflet/proj4leaflet.js` - proj4leaflet 1.0.2

External dependency:
- QUnit 2.20.0 (loaded from CDN: `https://code.jquery.com/qunit/`)

## Adding New Tests

To add tests for other frontend functions:

1. Create a new `test_<module>.html` file in this directory
2. Follow the structure of `test_crs_utils.html`:
   - Include QUnit CSS and JS from CDN
   - Load required vendored libraries
   - Include the code under test (inline or via `<script src="...">`)
   - Write QUnit tests in a `<script>` block
3. Update this README with the new test file details

## Continuous Integration

These tests are currently manual (browser-based). For CI automation, consider:

- **Playwright**: Headless browser testing
- **Puppeteer**: Chromium-based automation
- **Selenium**: Cross-browser testing

Example Playwright command:
```bash
npx playwright test tests/frontend/test_crs_utils.html
```

## References

- [QUnit Documentation](https://qunitjs.com/)
- [Leaflet Documentation](https://leafletjs.com/)
- [proj4js Documentation](http://proj4js.org/)
- [proj4leaflet GitHub](https://github.com/kartena/Proj4Leaflet)
