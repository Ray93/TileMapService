"""Locate a request tile in the source tile matrix and bundle layout."""
from tilemapservice.models.source import DataSource
from tilemapservice.models.tile import TileLocation, TileRequest
from tilemapservice.readers.bundle_reader import TileIndexCalculator
from tilemapservice.utils.coordinates import CoordinateTransformer, TileMatrixSet
from tilemapservice.utils.exceptions import InvalidTileRequestError, TileNotFoundError


class TileLocator:
    """Maps request matrix z/x/y to source level/x/y and bundle local index."""

    def __init__(self):
        self.coord = CoordinateTransformer()

    def locate(self, request: TileRequest, source: DataSource) -> TileLocation:
        if source.tile_matrix_set is None:
            raise InvalidTileRequestError("数据源缺少 Tile Matrix Set", {"source": source.name})

        request_matrix = self._get_request_matrix(request, source)
        x, y = request.x, request.y
        if request.service_type == "tms":
            y = request_matrix.tms_to_xyz_y(y, request.z)

        try:
            request_matrix.validate_tile(request.z, x, y)
        except ValueError as exc:
            raise InvalidTileRequestError(str(exc), request.__dict__) from exc

        center_x, center_y = request_matrix.tile_center_to_crs(x, y, request.z)
        min_x, min_y, max_x, max_y = request_matrix.tile_bounds_to_crs(x, y, request.z)

        source_center_x, source_center_y = self.coord.transform_point(
            center_x,
            center_y,
            request_matrix.crs,
            source.tile_matrix_set.crs,
        )

        corners = [
            self.coord.transform_point(min_x, min_y, request_matrix.crs, source.tile_matrix_set.crs),
            self.coord.transform_point(min_x, max_y, request_matrix.crs, source.tile_matrix_set.crs),
            self.coord.transform_point(max_x, min_y, request_matrix.crs, source.tile_matrix_set.crs),
            self.coord.transform_point(max_x, max_y, request_matrix.crs, source.tile_matrix_set.crs),
        ]
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        target_resolution = max(
            (max(xs) - min(xs)) / request_matrix.tile_width,
            (max(ys) - min(ys)) / request_matrix.tile_height,
        )

        source_level = source.tile_matrix_set.select_closest_level(abs(target_resolution))
        source_tile_x, source_tile_y = source.tile_matrix_set.crs_to_tile(
            source_center_x,
            source_center_y,
            source_level,
        )

        try:
            level_dir = source.get_level_dir(source_level)
        except FileNotFoundError as exc:
            raise TileNotFoundError("层级目录不存在", {"source": source.name, "source_level": source_level}) from exc

        bundle_path, local_row, local_col = TileIndexCalculator.find_bundle_path(level_dir, source_tile_x, source_tile_y)
        return TileLocation(
            request_x=x,
            request_y=y,
            source_level=source_level,
            source_tile_x=source_tile_x,
            source_tile_y=source_tile_y,
            local_row=local_row,
            local_col=local_col,
            bundle_path=bundle_path,
        )

    def _get_request_matrix(self, request: TileRequest, source: DataSource) -> TileMatrixSet:
        request_crs = self.coord.normalize_epsg(request.srs)

        if request.output_format not in ("auto", "png", "jpg", "jpeg"):
            raise InvalidTileRequestError("非法输出格式", request.__dict__)
        if request.service_type not in ("xyz", "tms"):
            raise InvalidTileRequestError("非法服务类型", request.__dict__)

        if request.matrix == "source":
            if source.tile_matrix_set is None or request_crs != source.tile_matrix_set.crs:
                raise InvalidTileRequestError("source matrix 要求请求 CRS 与数据源 CRS 一致", request.__dict__)
            return source.tile_matrix_set

        if request.matrix == "webmercator" and request_crs == "EPSG:3857":
            return TileMatrixSet("webmercator", "EPSG:3857", -20037508.342787, 20037508.342787)

        if request.matrix == "geographic" and request_crs == "EPSG:4326":
            return TileMatrixSet("geographic", "EPSG:4326", -180, 90)

        raise InvalidTileRequestError("请求 CRS 与 matrix 不匹配或 matrix 不受支持", request.__dict__)

