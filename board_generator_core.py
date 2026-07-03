#!/usr/bin/env python3
"""Internal shared implementation for calibration board PNG/SVG/DXF/STEP assets.

User-facing scripts should import this module instead of duplicating geometry
and export logic.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

try:
    import cv2
    import numpy as np
except ModuleNotFoundError as exc:
    missing = exc.name or "unknown"
    print(
        f"[ERROR] 当前 Python 环境缺少依赖：{missing}\n"
        "请先按 README.md 配置环境，例如：\n"
        "  conda env create -f environment.yml\n"
        "  conda activate charuco-board-generator",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


# ============================================================================
# 内部默认值
# ----------------------------------------------------------------------------
# 这些值由用户入口脚本覆盖。普通用户优先修改各 generate_*.py 文件。
# ============================================================================

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_PREFIX = ""
BOARD_TYPE = "charuco"
SQUARES_X = 11
SQUARES_Y = 8
SQUARE_MM = 20.0
MARKER_MM = 15.0
DICTIONARY = "DICT_5X5"
CIRCLES_X = 11
CIRCLES_Y = 8
CIRCLE_SPACING_MM = 20.0
CIRCLE_DIAMETER_MM = 8.0
MARKERS_X = 5
MARKERS_Y = 4
ARUCO_MARKER_MM = 30.0
MARKER_GAP_MM = 10.0
TAG_SPACING_RATIO = MARKER_GAP_MM / ARUCO_MARKER_MM
MARKER_BORDER_BITS = 1
FIRST_MARKER_ID = 0
FRAMED_FRAME_MARGIN_MM = 8.0
FRAMED_FRAME_WIDTH_MM = 2.0
FRAMED_TRIANGLE_ENABLED = True
FRAMED_TRIANGLE_BASE_MM = 20.0
FRAMED_TRIANGLE_HEIGHT_MM = 20.0
FRAMED_TRIANGLE_EDGE_GAP_MM = 0.0
BASE_WIDTH_MM = 240.0
BASE_HEIGHT_MM = 180.0
BASE_THICKNESS_MM = 5.0
BLACK_HEIGHT_MM = 0.5
BLACK_SHRINK_MM = 0.02
MIN_FEATURE_MM = 1.0
BLACK_GEOMETRY = "rectangles_no_gaps"
PIXELS_PER_SQUARE = 240
GENERATE_PNG = True
GENERATE_SVG = True
GENERATE_DXF = True
GENERATE_STEP = True
DXF_COLOR = "black"


ARUCO_DICTIONARIES = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
    "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
    "DICT_5X5": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
    "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
    "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
    "DICT_APRILTAG_16H5": cv2.aruco.DICT_APRILTAG_16H5,
    "DICT_APRILTAG_25H9": cv2.aruco.DICT_APRILTAG_25H9,
    "DICT_APRILTAG_36H10": cv2.aruco.DICT_APRILTAG_36H10,
    "DICT_APRILTAG_36H11": cv2.aruco.DICT_APRILTAG_36H11,
}

APRILTAG_DICTIONARIES = {
    "DICT_APRILTAG_16H5",
    "DICT_APRILTAG_25H9",
    "DICT_APRILTAG_36H10",
    "DICT_APRILTAG_36H11",
}


def resolve_black_geometry(args: argparse.Namespace) -> str:
    if args.black_geometry != "auto":
        return args.black_geometry
    if args.board_type == "aprilgrid" or args.dictionary in APRILTAG_DICTIONARIES:
        return "contours_filtered"
    return "rectangles_no_gaps"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fmt_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def fmt_token(value: float) -> str:
    return f"{value:g}".replace(".", "p")


def get_aruco_dictionary(name: str) -> cv2.aruco.Dictionary:
    try:
        dictionary_id = ARUCO_DICTIONARIES[name]
    except KeyError as exc:
        supported = ", ".join(sorted(ARUCO_DICTIONARIES))
        raise ValueError(f"不支持的 ArUco 字典：{name}。可选：{supported}") from exc
    return cv2.aruco.getPredefinedDictionary(dictionary_id)


def create_charuco_board(
    squares_x: int,
    squares_y: int,
    square_mm: float,
    marker_mm: float,
    dictionary_name: str,
) -> cv2.aruco.CharucoBoard:
    if squares_x < 3 or squares_y < 3:
        raise ValueError("ChArUco 方格数量 X/Y 都必须 >= 3。")
    if square_mm <= 0.0:
        raise ValueError("方格边长必须为正数。")
    if marker_mm <= 0.0:
        raise ValueError("marker 边长必须为正数。")
    if marker_mm >= square_mm:
        raise ValueError("marker 边长必须小于方格边长。")
    return cv2.aruco.CharucoBoard(
        (squares_x, squares_y),
        float(square_mm),
        float(marker_mm),
        get_aruco_dictionary(dictionary_name),
    )


def _auto_prefix(args: argparse.Namespace) -> str:
    if args.board_type == "chessboard":
        return (
            f"chessboard_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
            f"{args.squares_x}x{args.squares_y}_"
            f"{fmt_token(args.square_mm)}mm"
        )
    if args.board_type == "circle_grid":
        return (
            f"circle_grid_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
            f"{args.circles_x}x{args.circles_y}_"
            f"spacing{fmt_token(args.circle_spacing_mm)}mm_"
            f"dia{fmt_token(args.circle_diameter_mm)}mm"
        )
    if args.board_type == "asymmetric_circle_grid":
        return (
            f"asymmetric_circle_grid_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
            f"{args.circles_x}x{args.circles_y}_"
            f"spacing{fmt_token(args.circle_spacing_mm)}mm_"
            f"dia{fmt_token(args.circle_diameter_mm)}mm"
        )
    if args.board_type == "framed_circle_grid":
        return (
            f"framed_circle_grid_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
            f"{args.circles_x}x{args.circles_y}_"
            f"spacing{fmt_token(args.circle_spacing_mm)}mm_"
            f"dia{fmt_token(args.circle_diameter_mm)}mm"
        )
    if args.board_type == "aruco_marker_board":
        return (
            f"aruco_marker_board_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
            f"{args.markers_x}x{args.markers_y}_"
            f"{fmt_token(args.aruco_marker_mm)}mm_gap{fmt_token(args.marker_gap_mm)}mm_"
            f"id{args.first_marker_id}_{args.dictionary}"
        )
    if args.board_type == "aprilgrid":
        spacing_ratio = getattr(args, "tag_spacing_ratio", args.marker_gap_mm / args.aruco_marker_mm)
        return (
            f"aprilgrid_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
            f"{args.markers_x}x{args.markers_y}_"
            f"tag{fmt_token(args.aruco_marker_mm)}mm_"
            f"spacing{fmt_token(spacing_ratio)}_"
            f"id{args.first_marker_id}_{args.dictionary}"
        )
    return (
        f"charuco_board_{fmt_token(args.base_width_mm)}x{fmt_token(args.base_height_mm)}_"
        f"{args.squares_x}x{args.squares_y}_"
        f"{fmt_token(args.square_mm)}mm_{fmt_token(args.marker_mm)}mm"
    )


def default_prefix(args: argparse.Namespace) -> str:
    if args.output_prefix:
        return args.output_prefix
    return _auto_prefix(args)


def output_group_name(args: argparse.Namespace) -> str:
    if args.board_type == "charuco":
        return "charuco"
    if args.board_type == "chessboard":
        return "chessboard"
    if args.board_type == "circle_grid":
        return "circle_grid"
    if args.board_type == "asymmetric_circle_grid":
        return "asymmetric_circle_grid"
    if args.board_type == "aruco_marker_board":
        return "aruco_marker_board"
    if args.board_type == "aprilgrid":
        return "aprilgrid"
    if args.board_type == "framed_circle_grid":
        return "halcon"
    return args.board_type


def resolve_generation_output_dir(args: argparse.Namespace, prefix: str) -> Path:
    # Layout: outputs/<board-type>/<parameter-set>/...
    # The parameter folder is independent from --output-prefix, so different
    # parameter sets will not be mixed even when a custom file prefix is used.
    return args.output_dir / output_group_name(args) / _auto_prefix(args)




def pattern_size_mm(args: argparse.Namespace) -> tuple[float, float]:
    if args.board_type in {"circle_grid", "framed_circle_grid"}:
        return (
            (args.circles_x - 1) * args.circle_spacing_mm + args.circle_diameter_mm,
            (args.circles_y - 1) * args.circle_spacing_mm + args.circle_diameter_mm,
        )
    if args.board_type == "asymmetric_circle_grid":
        width_center_span = 2.0 * (args.circles_x - 1) * args.circle_spacing_mm
        if args.circles_y > 1:
            width_center_span += args.circle_spacing_mm
        return (
            width_center_span + args.circle_diameter_mm,
            (args.circles_y - 1) * args.circle_spacing_mm + args.circle_diameter_mm,
        )
    if args.board_type in {"aruco_marker_board", "aprilgrid"}:
        extra_gap_mm = args.marker_gap_mm if args.board_type == "aprilgrid" else 0.0
        return (
            args.markers_x * args.aruco_marker_mm + (args.markers_x - 1) * args.marker_gap_mm + 2.0 * extra_gap_mm,
            args.markers_y * args.aruco_marker_mm + (args.markers_y - 1) * args.marker_gap_mm + 2.0 * extra_gap_mm,
        )
    return args.squares_x * args.square_mm, args.squares_y * args.square_mm


def render_charuco_pattern(args: argparse.Namespace, px_to_mm: float) -> np.ndarray:
    board = create_charuco_board(
        args.squares_x,
        args.squares_y,
        args.square_mm,
        args.marker_mm,
        args.dictionary,
    )
    board_w_px = int(round(args.squares_x * args.square_mm / px_to_mm))
    board_h_px = int(round(args.squares_y * args.square_mm / px_to_mm))
    return board.generateImage((board_w_px, board_h_px), marginSize=0, borderBits=1)


def render_chessboard_pattern(args: argparse.Namespace, px_to_mm: float) -> np.ndarray:
    board_w_px = int(round(args.squares_x * args.square_mm / px_to_mm))
    board_h_px = int(round(args.squares_y * args.square_mm / px_to_mm))
    square_px = int(round(args.square_mm / px_to_mm))
    image = np.full((board_h_px, board_w_px), 255, dtype=np.uint8)
    for row in range(args.squares_y):
        for col in range(args.squares_x):
            if (row + col) % 2 != 0:
                continue
            x0 = col * square_px
            y0 = row * square_px
            image[y0 : y0 + square_px, x0 : x0 + square_px] = 0
    return image


def render_circle_grid_pattern(args: argparse.Namespace, px_to_mm: float) -> np.ndarray:
    pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
    pattern_w_px = int(round(pattern_w_mm / px_to_mm))
    pattern_h_px = int(round(pattern_h_mm / px_to_mm))
    image = np.full((pattern_h_px, pattern_w_px), 255, dtype=np.uint8)
    radius_px = int(round(args.circle_diameter_mm / 2.0 / px_to_mm))
    for x_mm, y_mm in circle_pattern_centers_mm(args):
        center = (int(round(x_mm / px_to_mm)), int(round(y_mm / px_to_mm)))
        cv2.circle(image, center, radius_px, 0, thickness=-1, lineType=cv2.LINE_8)
    return image


def render_aruco_marker_board_pattern(args: argparse.Namespace, px_to_mm: float) -> np.ndarray:
    pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
    pattern_w_px = int(round(pattern_w_mm / px_to_mm))
    pattern_h_px = int(round(pattern_h_mm / px_to_mm))
    image = np.full((pattern_h_px, pattern_w_px), 255, dtype=np.uint8)
    marker_px = int(round(args.aruco_marker_mm / px_to_mm))
    gap_px = int(round(args.marker_gap_mm / px_to_mm))
    dictionary = get_aruco_dictionary(args.dictionary)
    marker_id = args.first_marker_id
    start_px = gap_px if args.board_type == "aprilgrid" else 0
    for row in range(args.markers_y):
        for col in range(args.markers_x):
            marker_image = cv2.aruco.generateImageMarker(
                dictionary,
                int(marker_id),
                marker_px,
                borderBits=args.marker_border_bits,
            )
            x0 = start_px + col * (marker_px + gap_px)
            y0 = start_px + row * (marker_px + gap_px)
            image[y0 : y0 + marker_px, x0 : x0 + marker_px] = marker_image
            marker_id += 1
            if args.board_type == "aprilgrid" and gap_px > 0:
                corner_rects = [
                    (x0 - gap_px, y0 - gap_px),
                    (x0 + marker_px, y0 - gap_px),
                    (x0 + marker_px, y0 + marker_px),
                    (x0 - gap_px, y0 + marker_px),
                ]
                for sx, sy in corner_rects:
                    image[sy : sy + gap_px, sx : sx + gap_px] = 0
    return image


def framed_frame_rects_mm(args: argparse.Namespace, shrink_mm: float = 0.0) -> list[tuple[float, float, float, float]]:
    outer_x0 = args.frame_margin_mm + shrink_mm
    outer_y0 = args.frame_margin_mm + shrink_mm
    outer_x1 = args.base_width_mm - args.frame_margin_mm - shrink_mm
    outer_y1 = args.base_height_mm - args.frame_margin_mm - shrink_mm
    inner_x0 = args.frame_margin_mm + args.frame_width_mm - shrink_mm
    inner_y0 = args.frame_margin_mm + args.frame_width_mm - shrink_mm
    inner_x1 = args.base_width_mm - args.frame_margin_mm - args.frame_width_mm + shrink_mm
    inner_y1 = args.base_height_mm - args.frame_margin_mm - args.frame_width_mm + shrink_mm
    if outer_x0 >= outer_x1 or outer_y0 >= outer_y1 or inner_x0 >= inner_x1 or inner_y0 >= inner_y1:
        return []
    return [
        (outer_x0, outer_y0, outer_x1 - outer_x0, max(0.0, inner_y0 - outer_y0)),
        (outer_x0, inner_y0, max(0.0, inner_x0 - outer_x0), inner_y1 - inner_y0),
        (inner_x1, inner_y0, max(0.0, outer_x1 - inner_x1), inner_y1 - inner_y0),
        (outer_x0, inner_y1, outer_x1 - outer_x0, max(0.0, outer_y1 - inner_y1)),
    ]


def framed_frame_path_svg(args: argparse.Namespace) -> str:
    outer_x0 = args.frame_margin_mm
    outer_y0 = args.frame_margin_mm
    outer_x1 = args.base_width_mm - args.frame_margin_mm
    outer_y1 = args.base_height_mm - args.frame_margin_mm
    inner_x0 = args.frame_margin_mm + args.frame_width_mm
    inner_y0 = args.frame_margin_mm + args.frame_width_mm
    inner_x1 = args.base_width_mm - args.frame_margin_mm - args.frame_width_mm
    inner_y1 = args.base_height_mm - args.frame_margin_mm - args.frame_width_mm
    return (
        '    <path fill-rule="evenodd" d="'
        f"M {fmt_number(outer_x0)} {fmt_number(outer_y0)} "
        f"H {fmt_number(outer_x1)} V {fmt_number(outer_y1)} "
        f"H {fmt_number(outer_x0)} Z "
        f"M {fmt_number(inner_x0)} {fmt_number(inner_y0)} "
        f"V {fmt_number(inner_y1)} H {fmt_number(inner_x1)} "
        f"V {fmt_number(inner_y0)} Z"
        '"/>'
    )


def framed_triangle_points_mm(args: argparse.Namespace) -> list[tuple[float, float]]:
    left_x = args.frame_margin_mm + args.triangle_edge_gap_mm
    top_y = args.frame_margin_mm + args.triangle_edge_gap_mm
    return [
        (left_x, top_y),
        (left_x + args.triangle_base_mm, top_y),
        (left_x, top_y + args.triangle_height_mm),
    ]


def polygon_svg(points: list[tuple[float, float]]) -> str:
    point_text = " ".join(f"{fmt_number(x)},{fmt_number(y)}" for x, y in points)
    return f'    <polygon points="{point_text}"/>'


def draw_rect_mm(image: np.ndarray, px_to_mm: float, rect: tuple[float, float, float, float]) -> None:
    x_mm, y_mm, width_mm, height_mm = rect
    if width_mm <= 0.0 or height_mm <= 0.0:
        return
    x0 = int(round(x_mm / px_to_mm))
    y0 = int(round(y_mm / px_to_mm))
    x1 = int(round((x_mm + width_mm) / px_to_mm))
    y1 = int(round((y_mm + height_mm) / px_to_mm))
    image[y0:y1, x0:x1] = 0


def render_framed_circle_grid_image(args: argparse.Namespace, px_to_mm: float) -> np.ndarray:
    base_w_px = int(round(args.base_width_mm / px_to_mm))
    base_h_px = int(round(args.base_height_mm / px_to_mm))
    image = np.full((base_h_px, base_w_px), 255, dtype=np.uint8)
    radius_px = int(round(args.circle_diameter_mm / 2.0 / px_to_mm))
    for x_mm, y_mm in circle_centers_mm(args):
        center = (int(round(x_mm / px_to_mm)), int(round(y_mm / px_to_mm)))
        cv2.circle(image, center, radius_px, 0, thickness=-1, lineType=cv2.LINE_8)
    for rect in framed_frame_rects_mm(args):
        draw_rect_mm(image, px_to_mm, rect)
    if args.triangle_enabled:
        triangle_px = np.array(
            [[int(round(x / px_to_mm)), int(round(y / px_to_mm))] for x, y in framed_triangle_points_mm(args)],
            dtype=np.int32,
        )
        cv2.fillPoly(image, [triangle_px], 0, lineType=cv2.LINE_8)
    return image


def render_board_image(args: argparse.Namespace) -> tuple[np.ndarray, float, float, float]:
    pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
    if pattern_w_mm > args.base_width_mm or pattern_h_mm > args.base_height_mm:
        raise ValueError("内部标定区域尺寸不能大于白色基板尺寸。")

    if args.board_type in {"circle_grid", "asymmetric_circle_grid", "framed_circle_grid"}:
        scale_mm = args.circle_spacing_mm
    elif args.board_type in {"aruco_marker_board", "aprilgrid"}:
        scale_mm = args.aruco_marker_mm
    else:
        scale_mm = args.square_mm
    px_to_mm = scale_mm / args.pixels_per_square
    if args.board_type == "framed_circle_grid":
        board_image = render_framed_circle_grid_image(args, px_to_mm)
        return board_image, px_to_mm, args.base_width_mm, args.base_height_mm
    if args.board_type == "charuco":
        pattern_image = render_charuco_pattern(args, px_to_mm)
    elif args.board_type == "chessboard":
        pattern_image = render_chessboard_pattern(args, px_to_mm)
    elif args.board_type in {"circle_grid", "asymmetric_circle_grid"}:
        pattern_image = render_circle_grid_pattern(args, px_to_mm)
    elif args.board_type in {"aruco_marker_board", "aprilgrid"}:
        pattern_image = render_aruco_marker_board_pattern(args, px_to_mm)
    else:
        raise ValueError(f"不支持的标定板类型：{args.board_type}")

    pattern_h_px, pattern_w_px = pattern_image.shape[:2]
    base_w_px = int(round(args.base_width_mm / px_to_mm))
    base_h_px = int(round(args.base_height_mm / px_to_mm))
    margin_x_px = int(round((base_w_px - pattern_w_px) / 2.0))
    margin_y_px = int(round((base_h_px - pattern_h_px) / 2.0))
    full_image = np.full((base_h_px, base_w_px), 255, dtype=np.uint8)
    full_image[
        margin_y_px : margin_y_px + pattern_h_px,
        margin_x_px : margin_x_px + pattern_w_px,
    ] = pattern_image
    return full_image, px_to_mm, base_w_px * px_to_mm, base_h_px * px_to_mm


def mask_to_svg_rects(mask: np.ndarray, px_to_mm: float) -> str:
    rects: list[str] = []
    rect_h = fmt_number(px_to_mm)
    for y, row in enumerate(mask):
        xs = np.flatnonzero(row)
        if len(xs) == 0:
            continue
        run_start = int(xs[0])
        previous = int(xs[0])
        for x_value in xs[1:]:
            x = int(x_value)
            if x == previous + 1:
                previous = x
                continue
            rects.append(
                "    "
                f'<rect x="{fmt_number(run_start * px_to_mm)}" '
                f'y="{fmt_number(y * px_to_mm)}" '
                f'width="{fmt_number((previous - run_start + 1) * px_to_mm)}" '
                f'height="{rect_h}"/>'
            )
            run_start = x
            previous = x
        rects.append(
            "    "
            f'<rect x="{fmt_number(run_start * px_to_mm)}" '
            f'y="{fmt_number(y * px_to_mm)}" '
            f'width="{fmt_number((previous - run_start + 1) * px_to_mm)}" '
            f'height="{rect_h}"/>'
        )
    return "\n".join(rects)


def write_svg_layer(
    output_path: Path,
    width_mm: float,
    height_mm: float,
    rects: str,
    fill: str,
    label: str,
) -> None:
    ensure_dir(output_path.parent)
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{fmt_number(width_mm)}mm"
     height="{fmt_number(height_mm)}mm"
     viewBox="0 0 {fmt_number(width_mm)} {fmt_number(height_mm)}"
     version="1.1">
  <title>{label}</title>
  <g fill="{fill}">
{rects}
  </g>
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def write_svg_preview(
    output_path: Path,
    width_mm: float,
    height_mm: float,
    black_elements: str,
    white_elements: str,
) -> None:
    ensure_dir(output_path.parent)
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{fmt_number(width_mm)}mm"
     height="{fmt_number(height_mm)}mm"
     viewBox="0 0 {fmt_number(width_mm)} {fmt_number(height_mm)}"
     version="1.1">
  <title>Calibration board vector preview</title>
  <rect x="0" y="0" width="{fmt_number(width_mm)}" height="{fmt_number(height_mm)}" fill="#ffffff"/>
  <g fill="#ffffff">
{white_elements}
  </g>
  <g fill="#000000">
{black_elements}
  </g>
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def circle_pattern_centers_mm(args: argparse.Namespace) -> list[tuple[float, float]]:
    radius_mm = args.circle_diameter_mm / 2.0
    centers = []
    for row in range(args.circles_y):
        for col in range(args.circles_x):
            if args.board_type == "asymmetric_circle_grid":
                x_mm = radius_mm + (2 * col + row % 2) * args.circle_spacing_mm
            else:
                x_mm = radius_mm + col * args.circle_spacing_mm
            centers.append(
                (
                    x_mm,
                    radius_mm + row * args.circle_spacing_mm,
                )
            )
    return centers


def circle_centers_mm(args: argparse.Namespace) -> list[tuple[float, float]]:
    pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
    origin_x_mm = (args.base_width_mm - pattern_w_mm) / 2.0
    origin_y_mm = (args.base_height_mm - pattern_h_mm) / 2.0
    return [(origin_x_mm + x_mm, origin_y_mm + y_mm) for x_mm, y_mm in circle_pattern_centers_mm(args)]


def aruco_marker_origins_mm(args: argparse.Namespace) -> list[tuple[int, float, float]]:
    pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
    origin_x_mm = (args.base_width_mm - pattern_w_mm) / 2.0
    origin_y_mm = (args.base_height_mm - pattern_h_mm) / 2.0
    marker_start_x_mm = origin_x_mm + (args.marker_gap_mm if args.board_type == "aprilgrid" else 0.0)
    marker_start_y_mm = origin_y_mm + (args.marker_gap_mm if args.board_type == "aprilgrid" else 0.0)
    markers = []
    marker_id = args.first_marker_id
    for row in range(args.markers_y):
        for col in range(args.markers_x):
            markers.append(
                (
                    marker_id,
                    marker_start_x_mm + col * (args.aruco_marker_mm + args.marker_gap_mm),
                    marker_start_y_mm + row * (args.aruco_marker_mm + args.marker_gap_mm),
                )
            )
            marker_id += 1
    return markers


def aprilgrid_corner_square_rects_mm(args: argparse.Namespace, shrink_mm: float = 0.0) -> list[tuple[float, float, float, float]]:
    if args.board_type != "aprilgrid" or args.marker_gap_mm <= 0.0:
        return []
    square_mm = args.marker_gap_mm - 2.0 * shrink_mm
    if square_mm <= 0.0:
        return []

    rects = []
    seen: set[tuple[int, int]] = set()
    for _, marker_x_mm, marker_y_mm in aruco_marker_origins_mm(args):
        corners = [
            (marker_x_mm - args.marker_gap_mm, marker_y_mm - args.marker_gap_mm),
            (marker_x_mm + args.aruco_marker_mm, marker_y_mm - args.marker_gap_mm),
            (marker_x_mm + args.aruco_marker_mm, marker_y_mm + args.aruco_marker_mm),
            (marker_x_mm - args.marker_gap_mm, marker_y_mm + args.aruco_marker_mm),
        ]
        for x_mm, y_mm in corners:
            key = (round(x_mm * 1_000_000), round(y_mm * 1_000_000))
            if key in seen:
                continue
            seen.add(key)
            rects.append((x_mm + shrink_mm, y_mm + shrink_mm, square_mm, square_mm))
    return rects


def circle_grid_svg_elements(args: argparse.Namespace, radius_delta_mm: float = 0.0) -> str:
    radius_mm = max(0.0, args.circle_diameter_mm / 2.0 + radius_delta_mm)
    elements = []
    for x_mm, y_mm in circle_centers_mm(args):
        elements.append(
            "    "
            f'<circle cx="{fmt_number(x_mm)}" '
            f'cy="{fmt_number(y_mm)}" '
            f'r="{fmt_number(radius_mm)}"/>'
        )
    return "\n".join(elements)


def framed_circle_grid_svg_elements(args: argparse.Namespace) -> str:
    elements = [circle_grid_svg_elements(args), framed_frame_path_svg(args)]
    if args.triangle_enabled:
        elements.append(polygon_svg(framed_triangle_points_mm(args)))
    return "\n".join(item for item in elements if item)


def write_png(output_dir: Path, prefix: str, board_image: np.ndarray) -> Path:
    output_path = output_dir / f"{prefix}.png"
    ensure_dir(output_path.parent)
    if not cv2.imwrite(str(output_path), board_image):
        raise RuntimeError(f"写入 PNG 失败：{output_path}")
    return output_path


def write_svgs(
    output_dir: Path,
    prefix: str,
    board_image: np.ndarray,
    px_to_mm: float,
    width_mm: float,
    height_mm: float,
    args: argparse.Namespace,
) -> tuple[Path, Path, Path]:
    if args.board_type in {"circle_grid", "asymmetric_circle_grid"}:
        black_rects = circle_grid_svg_elements(args)
    elif args.board_type == "framed_circle_grid":
        black_rects = framed_circle_grid_svg_elements(args)
    else:
        black_rects = mask_to_svg_rects(board_image < 128, px_to_mm)
    white_rects = mask_to_svg_rects(board_image >= 128, px_to_mm)
    preview_output = output_dir / f"{prefix}.svg"
    black_output = output_dir / f"{prefix}_black.svg"
    white_output = output_dir / f"{prefix}_white.svg"
    write_svg_preview(preview_output, width_mm, height_mm, black_rects, white_rects)
    write_svg_layer(black_output, width_mm, height_mm, black_rects, "#000000", "Calibration board black regions")
    write_svg_layer(white_output, width_mm, height_mm, white_rects, "#ffffff", "Calibration board white regions")
    return preview_output, black_output, white_output


def compress_loop(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) <= 3:
        return points
    closed = points[0] == points[-1]
    work = points[:-1] if closed else points[:]
    compressed: list[tuple[int, int]] = []
    count = len(work)
    for index, point in enumerate(work):
        previous = work[index - 1]
        next_point = work[(index + 1) % count]
        if previous[0] == point[0] == next_point[0] or previous[1] == point[1] == next_point[1]:
            continue
        compressed.append(point)
    if closed and compressed:
        compressed.append(compressed[0])
    return compressed


def mask_to_boundary_loops(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    padded = np.pad(mask.astype(bool), 1, mode="constant", constant_values=False)
    top_edges = mask & ~padded[:-2, 1:-1]
    right_edges = mask & ~padded[1:-1, 2:]
    bottom_edges = mask & ~padded[2:, 1:-1]
    left_edges = mask & ~padded[1:-1, :-2]

    edge_map: defaultdict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for y, x in np.argwhere(top_edges):
        edge_map[(int(x), int(y))].append((int(x) + 1, int(y)))
    for y, x in np.argwhere(right_edges):
        edge_map[(int(x) + 1, int(y))].append((int(x) + 1, int(y) + 1))
    for y, x in np.argwhere(bottom_edges):
        edge_map[(int(x) + 1, int(y) + 1)].append((int(x), int(y) + 1))
    for y, x in np.argwhere(left_edges):
        edge_map[(int(x), int(y) + 1)].append((int(x), int(y)))

    loops: list[list[tuple[int, int]]] = []
    while edge_map:
        start = next(iter(edge_map))
        current = start
        loop = [start]
        while True:
            targets = edge_map.get(current)
            if not targets:
                break
            next_point = targets.pop()
            if not targets:
                del edge_map[current]
            loop.append(next_point)
            current = next_point
            if current == start:
                break
        if len(loop) >= 4 and loop[0] == loop[-1]:
            loops.append(compress_loop(loop))
    return loops


def offset_axis_aligned_line(
    start: tuple[float, float],
    end: tuple[float, float],
    shrink_mm: float,
) -> tuple[str, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if abs(dx) >= abs(dy):
        normal_y = 1.0 if dx > 0.0 else -1.0
        return ("y", start[1] + normal_y * shrink_mm)
    normal_x = -1.0 if dy > 0.0 else 1.0
    return ("x", start[0] + normal_x * shrink_mm)


def offset_loop_inward_mm(
    loop: list[tuple[int, int]],
    px_to_mm: float,
    shrink_mm: float,
) -> list[tuple[float, float]]:
    points_px = loop[:-1] if loop and loop[0] == loop[-1] else loop
    if len(points_px) < 3 or shrink_mm <= 0.0:
        return [(x * px_to_mm, y * px_to_mm) for x, y in points_px]

    points = [(x * px_to_mm, y * px_to_mm) for x, y in points_px]
    offset_points: list[tuple[float, float]] = []
    count = len(points)
    for index, point in enumerate(points):
        previous = points[index - 1]
        next_point = points[(index + 1) % count]
        in_line = offset_axis_aligned_line(previous, point, shrink_mm)
        out_line = offset_axis_aligned_line(point, next_point, shrink_mm)
        if in_line[0] == out_line[0]:
            continue
        if in_line[0] == "x":
            offset_points.append((in_line[1], out_line[1]))
        else:
            offset_points.append((out_line[1], in_line[1]))
    return dedupe_float_points(offset_points)


def dedupe_float_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or abs(deduped[-1][0] - point[0]) > 1e-9 or abs(deduped[-1][1] - point[1]) > 1e-9:
            deduped.append(point)
    if len(deduped) > 1 and abs(deduped[0][0] - deduped[-1][0]) <= 1e-9 and abs(deduped[0][1] - deduped[-1][1]) <= 1e-9:
        deduped.pop()
    return deduped


def write_dxf_layer(
    output_path: Path,
    width_mm: float,
    height_mm: float,
    px_to_mm: float,
    loops: list[list[tuple[int, int]]],
    layer_name: str,
    shrink_mm: float = 0.0,
) -> None:
    ensure_dir(output_path.parent)
    lines = [
        "0", "SECTION", "2", "HEADER",
        "9", "$INSUNITS", "70", "4",
        "9", "$EXTMIN", "10", "0", "20", "0", "30", "0",
        "9", "$EXTMAX", "10", fmt_number(width_mm), "20", fmt_number(height_mm), "30", "0",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]

    for loop in loops:
        points = offset_loop_inward_mm(loop, px_to_mm, shrink_mm)
        if len(points) < 3:
            continue
        lines.extend(["0", "LWPOLYLINE", "8", layer_name, "90", str(len(points)), "70", "1"])
        for x_mm, y_down_mm in points:
            lines.extend(["10", fmt_number(x_mm), "20", fmt_number(height_mm - y_down_mm)])

    lines.extend(["0", "ENDSEC", "0", "EOF"])
    output_path.write_text("\n".join(lines) + "\n", encoding="ascii")


def write_dxf_circle_layer(
    output_path: Path,
    width_mm: float,
    height_mm: float,
    args: argparse.Namespace,
    layer_name: str,
    shrink_mm: float = 0.0,
) -> None:
    ensure_dir(output_path.parent)
    radius_mm = args.circle_diameter_mm / 2.0 - shrink_mm
    if radius_mm <= 0.0:
        raise ValueError("圆点半径扣除内缩量后必须大于 0。")
    lines = [
        "0", "SECTION", "2", "HEADER",
        "9", "$INSUNITS", "70", "4",
        "9", "$EXTMIN", "10", "0", "20", "0", "30", "0",
        "9", "$EXTMAX", "10", fmt_number(width_mm), "20", fmt_number(height_mm), "30", "0",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]

    for x_mm, y_down_mm in circle_centers_mm(args):
        lines.extend(
            [
                "0", "CIRCLE",
                "8", layer_name,
                "10", fmt_number(x_mm),
                "20", fmt_number(height_mm - y_down_mm),
                "30", "0",
                "40", fmt_number(radius_mm),
            ]
        )

    lines.extend(["0", "ENDSEC", "0", "EOF"])
    output_path.write_text("\n".join(lines) + "\n", encoding="ascii")


def append_dxf_lwpolyline(
    lines: list[str],
    points: list[tuple[float, float]],
    height_mm: float,
    layer_name: str,
) -> None:
    if len(points) < 3:
        return
    lines.extend(["0", "LWPOLYLINE", "8", layer_name, "90", str(len(points)), "70", "1"])
    for x_mm, y_down_mm in points:
        lines.extend(["10", fmt_number(x_mm), "20", fmt_number(height_mm - y_down_mm)])


def framed_frame_boundary_points(args: argparse.Namespace, shrink_mm: float = 0.0) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    outer_x0 = args.frame_margin_mm + shrink_mm
    outer_y0 = args.frame_margin_mm + shrink_mm
    outer_x1 = args.base_width_mm - args.frame_margin_mm - shrink_mm
    outer_y1 = args.base_height_mm - args.frame_margin_mm - shrink_mm
    inner_x0 = args.frame_margin_mm + args.frame_width_mm - shrink_mm
    inner_y0 = args.frame_margin_mm + args.frame_width_mm - shrink_mm
    inner_x1 = args.base_width_mm - args.frame_margin_mm - args.frame_width_mm + shrink_mm
    inner_y1 = args.base_height_mm - args.frame_margin_mm - args.frame_width_mm + shrink_mm
    outer = [(outer_x0, outer_y0), (outer_x1, outer_y0), (outer_x1, outer_y1), (outer_x0, outer_y1)]
    inner = [(inner_x0, inner_y0), (inner_x0, inner_y1), (inner_x1, inner_y1), (inner_x1, inner_y0)]
    return outer, inner


def write_dxf_framed_circle_layer(
    output_path: Path,
    width_mm: float,
    height_mm: float,
    args: argparse.Namespace,
    layer_name: str,
    shrink_mm: float = 0.0,
) -> None:
    ensure_dir(output_path.parent)
    radius_mm = args.circle_diameter_mm / 2.0 - shrink_mm
    if radius_mm <= 0.0:
        raise ValueError("圆点半径扣除内缩量后必须大于 0。")
    lines = [
        "0", "SECTION", "2", "HEADER",
        "9", "$INSUNITS", "70", "4",
        "9", "$EXTMIN", "10", "0", "20", "0", "30", "0",
        "9", "$EXTMAX", "10", fmt_number(width_mm), "20", fmt_number(height_mm), "30", "0",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]

    for x_mm, y_down_mm in circle_centers_mm(args):
        lines.extend(
            [
                "0", "CIRCLE",
                "8", layer_name,
                "10", fmt_number(x_mm),
                "20", fmt_number(height_mm - y_down_mm),
                "30", "0",
                "40", fmt_number(radius_mm),
            ]
        )
    outer, inner = framed_frame_boundary_points(args, shrink_mm)
    append_dxf_lwpolyline(lines, outer, height_mm, layer_name)
    append_dxf_lwpolyline(lines, inner, height_mm, layer_name)
    if args.triangle_enabled:
        append_dxf_lwpolyline(lines, framed_triangle_points_mm(args), height_mm, layer_name)

    lines.extend(["0", "ENDSEC", "0", "EOF"])
    output_path.write_text("\n".join(lines) + "\n", encoding="ascii")


def write_dxfs(
    output_dir: Path,
    prefix: str,
    board_image: np.ndarray,
    px_to_mm: float,
    width_mm: float,
    height_mm: float,
    shrink_mm: float,
    color: str,
    args: argparse.Namespace,
) -> list[Path]:
    outputs: list[Path] = []
    shrink_token = f"_shrink{fmt_token(shrink_mm)}" if shrink_mm > 0.0 else ""
    if color in {"black", "both"}:
        black_output = output_dir / f"{prefix}{shrink_token}_black.dxf"
        if args.board_type in {"circle_grid", "asymmetric_circle_grid"}:
            write_dxf_circle_layer(black_output, width_mm, height_mm, args, "BLACK", shrink_mm)
        elif args.board_type == "framed_circle_grid":
            write_dxf_framed_circle_layer(black_output, width_mm, height_mm, args, "BLACK", shrink_mm)
        else:
            write_dxf_layer(
                black_output,
                width_mm,
                height_mm,
                px_to_mm,
                mask_to_boundary_loops(board_image < 128),
                "BLACK",
                shrink_mm,
            )
        outputs.append(black_output)
    if color in {"white", "both"}:
        white_output = output_dir / f"{prefix}_white.dxf"
        write_dxf_layer(
            white_output,
            width_mm,
            height_mm,
            px_to_mm,
            mask_to_boundary_loops(board_image >= 128),
            "WHITE",
            0.0,
        )
        outputs.append(white_output)
    return outputs


def marker_grid_size(dictionary_name: str) -> int:
    match = re.search(r"DICT_(\d+)X\1", dictionary_name)
    if match:
        return int(match.group(1))
    apriltag_match = re.search(r"DICT_APRILTAG_(\d+)H\d+", dictionary_name, flags=re.IGNORECASE)
    if apriltag_match:
        cell_count = int(apriltag_match.group(1))
        grid_size = int(math.isqrt(cell_count))
        if grid_size * grid_size == cell_count:
            return grid_size
    raise ValueError(f"无法从字典名称推断 marker 网格尺寸：{dictionary_name}")


def marker_black_cells(marker_id: int, dictionary_name: str, border_bits: int = 1) -> np.ndarray:
    payload_cells = marker_grid_size(dictionary_name)
    total_cells = payload_cells + 2 * border_bits
    sample_px_per_cell = 20
    marker_image = cv2.aruco.generateImageMarker(
        get_aruco_dictionary(dictionary_name),
        int(marker_id),
        total_cells * sample_px_per_cell,
        borderBits=border_bits,
    )
    cells = np.zeros((total_cells, total_cells), dtype=bool)
    for row in range(total_cells):
        for col in range(total_cells):
            y = int(round((row + 0.5) * sample_px_per_cell))
            x = int(round((col + 0.5) * sample_px_per_cell))
            cells[row, col] = marker_image[y, x] < 128
    return cells


def import_step_dependencies():
    try:
        import cadquery as cq
        from shapely.geometry import MultiPolygon, Polygon
        from shapely.ops import unary_union
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        print(
            f"[ERROR] 生成 STEP 需要额外依赖：{missing}\n"
            "请安装 requirements.txt，或使用 environment.yml 创建 conda 环境。",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return cq, Polygon, MultiPolygon, unary_union


def add_box(
    cq,
    solids: list,
    base_width_mm: float,
    base_height_mm: float,
    z_mm: float,
    height_mm: float,
    x_mm: float,
    y_down_mm: float,
    width_mm: float,
    depth_mm: float,
    min_feature_mm: float,
) -> bool:
    if width_mm <= min_feature_mm or depth_mm <= min_feature_mm:
        return False
    center_x = x_mm + width_mm / 2.0 - base_width_mm / 2.0
    center_y = base_height_mm / 2.0 - (y_down_mm + depth_mm / 2.0)
    solids.append(
        cq.Workplane("XY")
        .box(width_mm, depth_mm, height_mm, centered=(True, True, False))
        .translate((center_x, center_y, z_mm))
    )
    return True


def make_rectangle_step_solids(cq, board: cv2.aruco.CharucoBoard, args: argparse.Namespace) -> tuple[list, int]:
    board_w_mm = args.squares_x * args.square_mm
    board_h_mm = args.squares_y * args.square_mm
    margin_x_mm = (args.base_width_mm - board_w_mm) / 2.0
    margin_y_mm = (args.base_height_mm - board_h_mm) / 2.0
    solids: list = []
    skipped = 0

    for row in range(args.squares_y):
        for col in range(args.squares_x):
            if (row + col) % 2 != 0:
                continue
            ok = add_box(
                cq,
                solids,
                args.base_width_mm,
                args.base_height_mm,
                args.base_thickness_mm,
                args.black_height_mm,
                margin_x_mm + col * args.square_mm + args.black_shrink_mm,
                margin_y_mm + row * args.square_mm + args.black_shrink_mm,
                args.square_mm - 2.0 * args.black_shrink_mm,
                args.square_mm - 2.0 * args.black_shrink_mm,
                args.min_feature_mm,
            )
            skipped += 0 if ok else 1

    marker_ids = board.getIds().reshape(-1)
    marker_obj_points = board.getObjPoints()
    for marker_id, corners in zip(marker_ids, marker_obj_points):
        points = np.asarray(corners, dtype=float).reshape(-1, 3)
        marker_x_mm = float(np.min(points[:, 0]))
        marker_y_mm = float(np.min(points[:, 1]))
        cells = marker_black_cells(int(marker_id), args.dictionary)
        cell_mm = args.marker_mm / cells.shape[0]

        for cell_row in range(cells.shape[0]):
            for cell_col in range(cells.shape[1]):
                if not cells[cell_row, cell_col]:
                    continue
                left = args.black_shrink_mm if cell_col == 0 or not cells[cell_row, cell_col - 1] else 0.0
                right = args.black_shrink_mm if cell_col == cells.shape[1] - 1 or not cells[cell_row, cell_col + 1] else 0.0
                top = args.black_shrink_mm if cell_row == 0 or not cells[cell_row - 1, cell_col] else 0.0
                bottom = args.black_shrink_mm if cell_row == cells.shape[0] - 1 or not cells[cell_row + 1, cell_col] else 0.0
                ok = add_box(
                    cq,
                    solids,
                    args.base_width_mm,
                    args.base_height_mm,
                    args.base_thickness_mm,
                    args.black_height_mm,
                    margin_x_mm + marker_x_mm + cell_col * cell_mm + left,
                    margin_y_mm + marker_y_mm + cell_row * cell_mm + top,
                    cell_mm - left - right,
                    cell_mm - top - bottom,
                    args.min_feature_mm,
                )
                skipped += 0 if ok else 1
    return solids, skipped


def make_chessboard_step_solids(cq, args: argparse.Namespace) -> tuple[list, int]:
    board_w_mm = args.squares_x * args.square_mm
    board_h_mm = args.squares_y * args.square_mm
    margin_x_mm = (args.base_width_mm - board_w_mm) / 2.0
    margin_y_mm = (args.base_height_mm - board_h_mm) / 2.0
    solids: list = []
    skipped = 0
    for row in range(args.squares_y):
        for col in range(args.squares_x):
            if (row + col) % 2 != 0:
                continue
            ok = add_box(
                cq,
                solids,
                args.base_width_mm,
                args.base_height_mm,
                args.base_thickness_mm,
                args.black_height_mm,
                margin_x_mm + col * args.square_mm + args.black_shrink_mm,
                margin_y_mm + row * args.square_mm + args.black_shrink_mm,
                args.square_mm - 2.0 * args.black_shrink_mm,
                args.square_mm - 2.0 * args.black_shrink_mm,
                args.min_feature_mm,
            )
            skipped += 0 if ok else 1
    return solids, skipped


def make_circle_grid_step_solids(cq, args: argparse.Namespace) -> tuple[list, int]:
    radius_mm = args.circle_diameter_mm / 2.0 - args.black_shrink_mm
    if radius_mm * 2.0 <= args.min_feature_mm:
        return [], args.circles_x * args.circles_y

    solids: list = []
    for x_mm, y_down_mm in circle_centers_mm(args):
        center_x = x_mm - args.base_width_mm / 2.0
        center_y = args.base_height_mm / 2.0 - y_down_mm
        solids.append(
            cq.Workplane("XY")
            .circle(radius_mm)
            .extrude(args.black_height_mm)
            .translate((center_x, center_y, args.base_thickness_mm))
        )
    return solids, 0


def add_marker_cell_solids(
    cq,
    solids: list,
    args: argparse.Namespace,
    marker_id: int,
    marker_x_mm: float,
    marker_y_mm: float,
) -> int:
    cells = marker_black_cells(marker_id, args.dictionary, args.marker_border_bits)
    cell_mm = args.aruco_marker_mm / cells.shape[0]
    skipped = 0

    for cell_row in range(cells.shape[0]):
        for cell_col in range(cells.shape[1]):
            if not cells[cell_row, cell_col]:
                continue
            left = args.black_shrink_mm if cell_col == 0 or not cells[cell_row, cell_col - 1] else 0.0
            right = args.black_shrink_mm if cell_col == cells.shape[1] - 1 or not cells[cell_row, cell_col + 1] else 0.0
            top = args.black_shrink_mm if cell_row == 0 or not cells[cell_row - 1, cell_col] else 0.0
            bottom = args.black_shrink_mm if cell_row == cells.shape[0] - 1 or not cells[cell_row + 1, cell_col] else 0.0
            ok = add_box(
                cq,
                solids,
                args.base_width_mm,
                args.base_height_mm,
                args.base_thickness_mm,
                args.black_height_mm,
                marker_x_mm + cell_col * cell_mm + left,
                marker_y_mm + cell_row * cell_mm + top,
                cell_mm - left - right,
                cell_mm - top - bottom,
                args.min_feature_mm,
            )
            skipped += 0 if ok else 1
    return skipped


def make_aruco_marker_board_step_solids(cq, args: argparse.Namespace) -> tuple[list, int]:
    solids: list = []
    skipped = 0
    for marker_id, x_mm, y_mm in aruco_marker_origins_mm(args):
        skipped += add_marker_cell_solids(cq, solids, args, marker_id, x_mm, y_mm)
    for x_mm, y_mm, width_mm, depth_mm in aprilgrid_corner_square_rects_mm(args, args.black_shrink_mm):
        ok = add_box(
            cq,
            solids,
            args.base_width_mm,
            args.base_height_mm,
            args.base_thickness_mm,
            args.black_height_mm,
            x_mm,
            y_mm,
            width_mm,
            depth_mm,
            args.min_feature_mm,
        )
        skipped += 0 if ok else 1
    return solids, skipped


def add_polygon_prism(
    cq,
    solids: list,
    args: argparse.Namespace,
    points: list[tuple[float, float]],
    min_width_mm: float,
    min_height_mm: float,
) -> bool:
    if min_width_mm <= args.min_feature_mm or min_height_mm <= args.min_feature_mm:
        return False
    cad_points_2d = [(x - args.base_width_mm / 2.0, args.base_height_mm / 2.0 - y) for x, y in points]
    solids.append(
        cq.Workplane("XY")
        .polyline(cad_points_2d)
        .close()
        .extrude(args.black_height_mm)
        .translate((0, 0, args.base_thickness_mm))
    )
    return True


def make_framed_circle_grid_step_solids(cq, args: argparse.Namespace) -> tuple[list, int]:
    solids, skipped = make_circle_grid_step_solids(cq, args)
    for x_mm, y_mm, width_mm, depth_mm in framed_frame_rects_mm(args, args.black_shrink_mm):
        ok = add_box(
            cq,
            solids,
            args.base_width_mm,
            args.base_height_mm,
            args.base_thickness_mm,
            args.black_height_mm,
            x_mm,
            y_mm,
            width_mm,
            depth_mm,
            args.min_feature_mm,
        )
        skipped += 0 if ok else 1
    if args.triangle_enabled:
        ok = add_polygon_prism(
            cq,
            solids,
            args,
            framed_triangle_points_mm(args),
            args.triangle_base_mm,
            args.triangle_height_mm,
        )
        skipped += 0 if ok else 1
    return solids, skipped


def polygon_area(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )


def polygon_feature_large_enough(polygon, min_feature_mm: float) -> bool:
    if polygon.is_empty:
        return False
    min_x, min_y, max_x, max_y = polygon.bounds
    return (max_x - min_x) > min_feature_mm and (max_y - min_y) > min_feature_mm and polygon.area > min_feature_mm**2


def make_wire(cq, points: Iterable[tuple[float, float, float]]):
    return cq.Wire.makePolygon([cq.Vector(*point) for point in points], close=True)


def orient_points(points: list[tuple[float, float, float]], ccw: bool) -> list[tuple[float, float, float]]:
    area = polygon_area([(x, y) for x, y, _ in points])
    if (ccw and area < 0.0) or (not ccw and area > 0.0):
        return list(reversed(points))
    return points


def cad_points(coords: list[tuple[float, float]], args: argparse.Namespace, z_mm: float) -> list[tuple[float, float, float]]:
    return [(x - args.base_width_mm / 2.0, args.base_height_mm / 2.0 - y, z_mm) for x, y in coords]


def iter_polygons(geometry, Polygon, MultiPolygon) -> list:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    geoms = getattr(geometry, "geoms", None)
    if geoms is None:
        return []
    polygons = []
    for item in geoms:
        polygons.extend(iter_polygons(item, Polygon, MultiPolygon))
    return polygons


def make_contour_step_solids(cq, Polygon, MultiPolygon, unary_union, board_image: np.ndarray, px_to_mm: float, args: argparse.Namespace, filtered: bool) -> tuple[list, int]:
    positive_loops: list[dict[str, object]] = []
    negative_loops: list[dict[str, object]] = []
    for loop in mask_to_boundary_loops(board_image < 128):
        raw_points = loop[:-1] if loop and loop[0] == loop[-1] else loop
        if len(raw_points) < 3:
            continue
        raw_area = polygon_area([(float(x), float(y)) for x, y in raw_points])
        points_mm = [(x * px_to_mm, y * px_to_mm) for x, y in raw_points]
        polygon = Polygon(points_mm)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        item = {
            "points": points_mm,
            "polygon": polygon,
            "area": abs(polygon.area),
            "sample": polygon.representative_point(),
            "holes": [],
        }
        if raw_area > 0.0:
            positive_loops.append(item)
        else:
            negative_loops.append(item)

    for hole in negative_loops:
        sample = hole["sample"]
        parents = [
            outer
            for outer in positive_loops
            if outer["polygon"].contains(sample)  # type: ignore[union-attr]
        ]
        if not parents:
            continue
        parent = min(parents, key=lambda outer: outer["area"])  # type: ignore[index]
        parent["holes"].append(hole)  # type: ignore[union-attr]

    polygons = []
    for outer in positive_loops:
        holes = [hole["points"] for hole in outer["holes"]]  # type: ignore[index, union-attr]
        polygon = Polygon(outer["points"], holes)  # type: ignore[arg-type]
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        polygons.extend(iter_polygons(polygon, Polygon, MultiPolygon))

    geometry = unary_union(polygons) if polygons else Polygon()
    if args.black_shrink_mm > 0.0:
        geometry = geometry.buffer(-args.black_shrink_mm, join_style=2, mitre_limit=5.0)
    if not geometry.is_valid:
        geometry = geometry.buffer(0)

    solids = []
    skipped = 0
    for polygon in iter_polygons(geometry, Polygon, MultiPolygon):
        if filtered and not polygon_feature_large_enough(polygon, args.min_feature_mm):
            skipped += 1
            continue
        exterior = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]
        outer_points = orient_points(cad_points(exterior, args, args.base_thickness_mm), ccw=True)
        try:
            outer_wire = make_wire(cq, outer_points)
        except Exception:
            skipped += 1
            continue
        inner_wires = []
        for interior in polygon.interiors:
            hole_polygon = Polygon(interior)
            if filtered and not polygon_feature_large_enough(hole_polygon, args.min_feature_mm):
                continue
            hole = [(float(x), float(y)) for x, y in list(interior.coords)[:-1]]
            hole_points = orient_points(cad_points(hole, args, args.base_thickness_mm), ccw=False)
            try:
                inner_wires.append(make_wire(cq, hole_points))
            except Exception:
                skipped += 1
        try:
            face = cq.Face.makeFromWires(outer_wire, inner_wires)
            solids.append(cq.Solid.extrudeLinear(face.outerWire(), face.innerWires(), (0, 0, args.black_height_mm)))
        except Exception:
            skipped += 1
    return solids, skipped


def write_step(output_dir: Path, prefix: str, args: argparse.Namespace) -> tuple[Path, int, int]:
    cq, Polygon, MultiPolygon, unary_union = import_step_dependencies()
    base = cq.Workplane("XY").box(
        args.base_width_mm,
        args.base_height_mm,
        args.base_thickness_mm,
        centered=(True, True, False),
    )

    if args.board_type == "charuco" and args.black_geometry == "rectangles_no_gaps":
        board = create_charuco_board(args.squares_x, args.squares_y, args.square_mm, args.marker_mm, args.dictionary)
        black_solids, skipped = make_rectangle_step_solids(cq, board, args)
    elif args.board_type == "chessboard" and args.black_geometry == "rectangles_no_gaps":
        black_solids, skipped = make_chessboard_step_solids(cq, args)
    elif args.board_type in {"circle_grid", "asymmetric_circle_grid"} and args.black_geometry == "rectangles_no_gaps":
        black_solids, skipped = make_circle_grid_step_solids(cq, args)
    elif args.board_type == "framed_circle_grid" and args.black_geometry == "rectangles_no_gaps":
        black_solids, skipped = make_framed_circle_grid_step_solids(cq, args)
    elif args.board_type in {"aruco_marker_board", "aprilgrid"} and args.black_geometry == "rectangles_no_gaps":
        black_solids, skipped = make_aruco_marker_board_step_solids(cq, args)
    else:
        board_image, px_to_mm, _, _ = render_board_image(args)
        black_solids, skipped = make_contour_step_solids(
            cq,
            Polygon,
            MultiPolygon,
            unary_union,
            board_image,
            px_to_mm,
            args,
            filtered=True,
        )

    assembly = cq.Assembly(name=f"{args.board_type}_board")
    assembly.add(base, name="white_base", color=cq.Color(1.0, 1.0, 1.0))
    for index, solid in enumerate(black_solids):
        assembly.add(solid, name=f"black_{index:04d}", color=cq.Color(0.0, 0.0, 0.0))

    output_path = output_dir / (
        f"{prefix}_base{fmt_token(args.base_thickness_mm)}_"
        f"black{fmt_token(args.black_height_mm)}_"
        f"shrink{fmt_token(args.black_shrink_mm)}_"
        f"{args.black_geometry}.step"
    )
    ensure_dir(output_path.parent)
    assembly.save(str(output_path), exportType="STEP")
    return output_path, len(black_solids), skipped


def fmt_meter(value: float) -> str:
    if abs(value) < 1e-15:
        value = 0.0
    return f"{value:.12g}"


def resolve_output_file(output_dir: Path, file_name: str | Path) -> Path:
    path = Path(file_name)
    if not path.is_absolute():
        path = output_dir / path
    ensure_dir(path.parent)
    return path


def write_halcon_descr(output_dir: Path, args: argparse.Namespace, file_name: str | Path) -> Path:
    output_path = resolve_output_file(output_dir, file_name)
    mark_dist_m = args.circle_spacing_mm / 1000.0
    radius_m = args.circle_diameter_mm / 2000.0
    base_w_m = args.base_width_mm / 1000.0
    base_h_m = args.base_height_mm / 1000.0
    frame_margin_m = args.frame_margin_mm / 1000.0
    frame_width_m = args.frame_width_mm / 1000.0

    frame_min_x = -base_w_m / 2.0 + frame_margin_m
    frame_max_x = base_w_m / 2.0 - frame_margin_m
    frame_min_y = -base_h_m / 2.0 + frame_margin_m
    frame_max_y = base_h_m / 2.0 - frame_margin_m
    plate_min_x = -base_w_m / 2.0
    plate_max_x = base_w_m / 2.0
    plate_min_y = -base_h_m / 2.0
    plate_max_y = base_h_m / 2.0

    lines = [
        "# Plate Description Version 2",
        "# Description of the standard calibration plate",
        "# used for the camera calibration in HALCON",
        "# (generated by charuco_board_generator)",
        "#",
        f"# {args.circles_y} rows x {args.circles_x} columns",
        (
            "# Width, height of the black frame [meter]: "
            f"{fmt_meter(frame_max_x - frame_min_x)}, {fmt_meter(frame_max_y - frame_min_y)}"
        ),
        f"# Distance between mark centers [meter]: {fmt_meter(mark_dist_m)}",
        "",
        "# Number of marks in y-dimension (rows)",
        f"r {args.circles_y}",
        "",
        "# Number of marks in x-dimension (columns)",
        f"c {args.circles_x}",
        "#   offset of coordinate system in z-dimension [meter] (optional):",
        "z 0",
        "# Rectangular border (rim and black frame) of calibration plate",
        "#   rim of the calibration plate (min x, max y, max x, min y) [meter]:",
        f"o {fmt_meter(plate_min_x)} {fmt_meter(plate_max_y)} {fmt_meter(plate_max_x)} {fmt_meter(plate_min_y)}",
        "#   outer border of the black frame (min x, max y, max x, min y) [meter]:",
        f"i {fmt_meter(frame_min_x)} {fmt_meter(frame_max_y)} {fmt_meter(frame_max_x)} {fmt_meter(frame_min_y)}",
    ]
    if args.triangle_enabled:
        t1_x = frame_min_x
        t1_y = frame_min_y + args.triangle_height_mm / 1000.0
        t2_x = frame_min_x + args.triangle_base_mm / 1000.0
        t2_y = frame_min_y
        lines.extend(
            [
                "#   triangular corner mark given by two corner points (x,y, x,y) [meter]",
                "#   (optional):",
                f"t {fmt_meter(t1_x)} {fmt_meter(t1_y)} {fmt_meter(t2_x)} {fmt_meter(t2_y)}",
            ]
        )
    lines.extend(
        [
            "",
            "#   width of the black frame [meter]:",
            f"w {fmt_meter(frame_width_m)}",
            "# calibration marks:  x y radius [meter]",
            "",
        ]
    )

    x0 = -((args.circles_x - 1) / 2.0) * mark_dist_m
    y0 = -((args.circles_y - 1) / 2.0) * mark_dist_m
    for row in range(args.circles_y):
        y_m = y0 + row * mark_dist_m
        lines.append(f"# calibration marks at y = {fmt_meter(y_m)} m")
        for col in range(args.circles_x):
            x_m = x0 + col * mark_dist_m
            lines.append(f"{fmt_meter(x_m)} {fmt_meter(y_m)} {fmt_meter(radius_m)}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="ascii")
    return output_path


def write_halcon_ps(output_dir: Path, args: argparse.Namespace, file_name: str | Path) -> Path:
    output_path = resolve_output_file(output_dir, file_name)
    pt_per_mm = 72.0 / 25.4
    width_pt = args.base_width_mm * pt_per_mm
    height_pt = args.base_height_mm * pt_per_mm

    def pt(value_mm: float) -> str:
        return fmt_number(value_mm * pt_per_mm)

    def rect_path(x_mm: float, y_down_mm: float, w_mm: float, h_mm: float) -> str:
        y_pt = (args.base_height_mm - y_down_mm - h_mm) * pt_per_mm
        return (
            f"newpath {pt(x_mm)} {fmt_number(y_pt)} moveto "
            f"{pt(w_mm)} 0 rlineto 0 {pt(h_mm)} rlineto "
            f"{fmt_number(-w_mm * pt_per_mm)} 0 rlineto closepath"
        )

    lines = [
        "%!PS-Adobe-3.0",
        f"%%BoundingBox: 0 0 {math.ceil(width_pt)} {math.ceil(height_pt)}",
        "%%Pages: 1",
        "%%EndComments",
        "<< /PageSize [" + fmt_number(width_pt) + " " + fmt_number(height_pt) + "] >> setpagedevice",
        "1 setgray",
        rect_path(0.0, 0.0, args.base_width_mm, args.base_height_mm),
        "fill",
        "0 setgray",
    ]

    outer_w = args.base_width_mm - 2.0 * args.frame_margin_mm
    outer_h = args.base_height_mm - 2.0 * args.frame_margin_mm
    lines.extend([rect_path(args.frame_margin_mm, args.frame_margin_mm, outer_w, outer_h), "fill"])
    inner_x = args.frame_margin_mm + args.frame_width_mm
    inner_y = args.frame_margin_mm + args.frame_width_mm
    inner_w = args.base_width_mm - 2.0 * inner_x
    inner_h = args.base_height_mm - 2.0 * inner_y
    lines.extend(["1 setgray", rect_path(inner_x, inner_y, inner_w, inner_h), "fill", "0 setgray"])

    if args.triangle_enabled:
        points = framed_triangle_points_mm(args)
        first_x, first_y = points[0]
        lines.append(f"newpath {pt(first_x)} {pt(args.base_height_mm - first_y)} moveto")
        for x_mm, y_mm in points[1:]:
            lines.append(f"{pt(x_mm)} {pt(args.base_height_mm - y_mm)} lineto")
        lines.extend(["closepath", "fill"])

    radius_mm = args.circle_diameter_mm / 2.0
    for x_mm, y_mm in circle_centers_mm(args):
        lines.append(
            f"newpath {pt(x_mm)} {pt(args.base_height_mm - y_mm)} "
            f"{pt(radius_mm)} 0 360 arc fill"
        )

    lines.extend(["showpage", "%%EOF"])
    output_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return output_path


def write_aprilgrid_yaml(output_dir: Path, args: argparse.Namespace, file_name: str | Path) -> Path:
    output_path = resolve_output_file(output_dir, file_name)
    tag_size_m = args.aruco_marker_mm / 1000.0
    tag_spacing_ratio = getattr(args, "tag_spacing_ratio", args.marker_gap_mm / args.aruco_marker_mm)
    lines = [
        "target_type: 'aprilgrid'",
        f"tagCols: {args.markers_x}",
        f"tagRows: {args.markers_y}",
        f"tagSize: {fmt_meter(tag_size_m)}",
        f"tagSpacing: {fmt_meter(tag_spacing_ratio)}",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return output_path


def make_args(**overrides) -> argparse.Namespace:
    values = {
        "output_dir": OUTPUT_DIR,
        "output_prefix": OUTPUT_PREFIX,
        "board_type": BOARD_TYPE,
        "squares_x": SQUARES_X,
        "squares_y": SQUARES_Y,
        "square_mm": SQUARE_MM,
        "marker_mm": MARKER_MM,
        "dictionary": DICTIONARY,
        "circles_x": CIRCLES_X,
        "circles_y": CIRCLES_Y,
        "circle_spacing_mm": CIRCLE_SPACING_MM,
        "circle_diameter_mm": CIRCLE_DIAMETER_MM,
        "markers_x": MARKERS_X,
        "markers_y": MARKERS_Y,
        "aruco_marker_mm": ARUCO_MARKER_MM,
        "marker_gap_mm": MARKER_GAP_MM,
        "tag_spacing_ratio": TAG_SPACING_RATIO,
        "marker_border_bits": MARKER_BORDER_BITS,
        "first_marker_id": FIRST_MARKER_ID,
        "frame_margin_mm": FRAMED_FRAME_MARGIN_MM,
        "frame_width_mm": FRAMED_FRAME_WIDTH_MM,
        "triangle_enabled": FRAMED_TRIANGLE_ENABLED,
        "triangle_base_mm": FRAMED_TRIANGLE_BASE_MM,
        "triangle_height_mm": FRAMED_TRIANGLE_HEIGHT_MM,
        "triangle_edge_gap_mm": FRAMED_TRIANGLE_EDGE_GAP_MM,
        "base_width_mm": BASE_WIDTH_MM,
        "base_height_mm": BASE_HEIGHT_MM,
        "base_thickness_mm": BASE_THICKNESS_MM,
        "black_height_mm": BLACK_HEIGHT_MM,
        "black_shrink_mm": BLACK_SHRINK_MM,
        "min_feature_mm": MIN_FEATURE_MM,
        "black_geometry": BLACK_GEOMETRY,
        "pixels_per_square": PIXELS_PER_SQUARE,
        "dxf_color": DXF_COLOR,
        "no_png": not GENERATE_PNG,
        "no_svg": not GENERATE_SVG,
        "no_dxf": not GENERATE_DXF,
        "no_step": not GENERATE_STEP,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def validate_args(args: argparse.Namespace) -> None:
    if args.base_width_mm <= 0.0 or args.base_height_mm <= 0.0:
        raise ValueError("基板长宽必须为正数。")
    if args.base_thickness_mm <= 0.0:
        raise ValueError("基板厚度必须为正数。")
    if args.black_height_mm <= 0.0:
        raise ValueError("黑色凸起高度必须为正数。")
    if args.black_shrink_mm < 0.0:
        raise ValueError("黑色内缩量不能为负数。")
    if args.min_feature_mm < 0.0:
        raise ValueError("最小特征尺寸不能为负数。")
    if args.pixels_per_square <= 0:
        raise ValueError("pixels-per-square 必须为正整数。")
    if args.black_geometry not in {"rectangles_no_gaps", "contours_filtered"}:
        raise ValueError("STEP 建模方式只支持 rectangles_no_gaps 或 contours_filtered。")
    if args.marker_border_bits <= 0:
        raise ValueError("marker border bits 必须为正整数。")

    if args.board_type in {"charuco", "chessboard"}:
        if args.squares_x < 2 or args.squares_y < 2:
            raise ValueError("棋盘/ChArUco 方格数量 X/Y 都必须 >= 2。")
        if args.square_mm <= 0.0:
            raise ValueError("方格边长必须为正数。")
        if args.board_type == "charuco":
            if args.squares_x < 3 or args.squares_y < 3:
                raise ValueError("ChArUco 方格数量 X/Y 都必须 >= 3。")
            if args.marker_mm <= 0.0:
                raise ValueError("marker 边长必须为正数。")
            if args.marker_mm >= args.square_mm:
                raise ValueError("marker 边长必须小于方格边长。")

    if args.board_type in {"circle_grid", "asymmetric_circle_grid", "framed_circle_grid"}:
        if args.circles_x < 2 or args.circles_y < 2:
            raise ValueError("圆点板圆点数量 X/Y 都必须 >= 2。")
        if args.circle_spacing_mm <= 0.0:
            raise ValueError("圆点间距必须为正数。")
        if args.circle_diameter_mm <= 0.0:
            raise ValueError("圆点直径必须为正数。")
        if args.circle_diameter_mm >= args.circle_spacing_mm:
            raise ValueError("圆点直径建议小于圆心间距，避免圆点相连。")

    if args.board_type in {"aruco_marker_board", "aprilgrid"}:
        if args.markers_x < 1 or args.markers_y < 1:
            raise ValueError("标记板横向/纵向 marker 数量都必须 >= 1。")
        if args.aruco_marker_mm <= 0.0:
            raise ValueError("marker 边长必须为正数。")
        if args.marker_gap_mm < 0.0:
            raise ValueError("marker 间距不能为负数。")
        if args.first_marker_id < 0:
            raise ValueError("起始 marker id 不能为负数。")
        if args.board_type == "aprilgrid" and args.dictionary not in APRILTAG_DICTIONARIES:
            supported = ", ".join(sorted(APRILTAG_DICTIONARIES))
            raise ValueError(f"Aprilgrid 只能使用 AprilTag 字典。可选：{supported}")
        dictionary = get_aruco_dictionary(args.dictionary)
        marker_count = int(dictionary.bytesList.shape[0])
        required_end_id = args.first_marker_id + args.markers_x * args.markers_y - 1
        if required_end_id >= marker_count:
            raise ValueError(
                f"ArUco marker id 超出字典范围：需要到 {required_end_id}，"
                f"{args.dictionary} 只有 0..{marker_count - 1}。"
            )

    if args.board_type == "framed_circle_grid":
        if args.frame_margin_mm < 0.0:
            raise ValueError("带框圆点板外框边距不能为负数。")
        if args.frame_width_mm <= 0.0:
            raise ValueError("带框圆点板外框线宽必须为正数。")
        if args.frame_width_mm <= 2.0 * args.black_shrink_mm:
            raise ValueError("带框圆点板外框线宽必须大于 2 倍黑色内缩量。")
        if 2.0 * (args.frame_margin_mm + args.frame_width_mm) >= args.base_width_mm:
            raise ValueError("带框圆点板外框边距和线宽过大，已超过基板可用空间。")
        if args.triangle_enabled:
            if args.triangle_base_mm <= 0.0 or args.triangle_height_mm <= 0.0:
                raise ValueError("带框圆点板三角标识底边和高度必须为正数。")
            if args.triangle_edge_gap_mm < 0.0:
                raise ValueError("带框圆点板三角标识边缘间距不能为负数。")
            if args.triangle_edge_gap_mm + args.triangle_base_mm >= args.base_width_mm - 2.0 * args.frame_margin_mm:
                raise ValueError("带框圆点板三角标识横向尺寸过大。")
            if args.triangle_edge_gap_mm + args.triangle_height_mm >= args.base_height_mm - 2.0 * args.frame_margin_mm:
                raise ValueError("带框圆点板三角标识纵向尺寸过大。")
        pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
        if (args.base_width_mm - pattern_w_mm) / 2.0 < args.frame_margin_mm + args.frame_width_mm:
            raise ValueError("圆点区域横向离外框太近，请增大基板尺寸或减小圆点数量/间距。")
        if (args.base_height_mm - pattern_h_mm) / 2.0 < args.frame_margin_mm + args.frame_width_mm:
            raise ValueError("圆点区域纵向离外框太近，请增大基板尺寸或减小圆点数量/间距。")

    pattern_w_mm, pattern_h_mm = pattern_size_mm(args)
    if pattern_w_mm > args.base_width_mm or pattern_h_mm > args.base_height_mm:
        raise ValueError("内部标定图案尺寸不能大于基板外形尺寸。")


def _run_generation(args: argparse.Namespace) -> int:
    args.black_geometry = resolve_black_geometry(args)
    validate_args(args)

    prefix = default_prefix(args)
    output_dir = resolve_generation_output_dir(args, prefix)
    args.resolved_output_dir = output_dir
    ensure_dir(output_dir)
    print(f"[INFO] Output directory: {output_dir}")

    need_2d = not args.no_png or not args.no_svg or not args.no_dxf
    if need_2d:
        board_image, px_to_mm, width_mm, height_mm = render_board_image(args)
        print(f"[INFO] 2D physical size: {width_mm:.3f} mm x {height_mm:.3f} mm")
        if not args.no_png:
            print(f"[SUCCESS] PNG: {write_png(output_dir, prefix, board_image)}")
        if not args.no_svg:
            preview, black_svg, white_svg = write_svgs(output_dir, prefix, board_image, px_to_mm, width_mm, height_mm, args)
            print(f"[SUCCESS] SVG preview: {preview}")
            print(f"[SUCCESS] SVG black: {black_svg}")
            print(f"[SUCCESS] SVG white: {white_svg}")
        if not args.no_dxf:
            for path in write_dxfs(
                output_dir,
                prefix,
                board_image,
                px_to_mm,
                width_mm,
                height_mm,
                args.black_shrink_mm,
                args.dxf_color,
                args,
            ):
                print(f"[SUCCESS] DXF: {path}")

    if not args.no_step:
        step_path, black_count, skipped = write_step(output_dir, prefix, args)
        print(f"[SUCCESS] STEP: {step_path}")
        print(f"[INFO] STEP black solids: {black_count}, skipped tiny/invalid features: {skipped}")

    print("[SUCCESS] Calibration board asset generation complete.")
    return 0


def run_generation(args: argparse.Namespace) -> int:
    try:
        return _run_generation(args)
    except ValueError as exc:
        print(f"[ERROR] 参数无效：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    print(
        "This is an internal module. Please run one of:\n"
        "  python generate_charuco_board.py\n"
        "  python generate_chess_board.py\n"
        "  python generate_circle_grid_board.py\n"
        "  python generate_asymmetric_circle_grid_board.py\n"
        "  python generate_aruco_marker_board.py\n"
        "  python generate_aprilgrid_board.py\n"
        "  python generate_halcon_board.py"
    )

