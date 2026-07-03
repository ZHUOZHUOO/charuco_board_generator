#!/usr/bin/env python3
"""Generate a ChArUco calibration board."""

from __future__ import annotations

import argparse
from pathlib import Path

import board_generator_core as core


# ============================================================================
# 用户常改参数区：ChArUco 标定板
# ----------------------------------------------------------------------------
# 所有尺寸单位都是 mm；STEP/DXF 也都以 mm 为单位。
# 临时修改参数时，也可以使用命令行参数覆盖下面的默认值。
# ============================================================================

# 输出目录：所有生成文件默认写到这里。
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"

# 输出文件名前缀。留空时脚本会根据尺寸自动生成。
OUTPUT_PREFIX = ""

# ChArUco 方格数量。X 是横向方格数，Y 是纵向方格数。
SQUARES_X = 11
SQUARES_Y = 8

# 每个棋盘方格边长。相机标定时也要使用这个真实尺寸。
SQUARE_MM = 20.0

# ArUco marker 边长，必须小于 SQUARE_MM。
MARKER_MM = 15.0

# ArUco 字典。DICT_5X5 会映射到 OpenCV DICT_5X5_50。
DICTIONARY = "DICT_5X5"

# 白色基板外形尺寸。
# 默认：内部标定区域 220 x 160 mm，基板 240 x 180 mm，四周边距 10 mm。
BASE_WIDTH_MM = 240.0
BASE_HEIGHT_MM = 180.0

# 白色基板厚度。STEP 中白色基板从 Z=0 拉伸到该高度。
BASE_THICKNESS_MM = 3.0

# 黑色图案凸起高度。STEP 总高度 = BASE_THICKNESS_MM + BLACK_HEIGHT_MM。
BLACK_HEIGHT_MM = 0.5

# 黑色轮廓向内缩小量。用于避免黑白区域角点相切导致薄壁/零厚度问题。
BLACK_SHRINK_MM = 0.02

# STEP 最小黑色特征尺寸。任一边小于该值的小黑块不会导出。
# 可过滤 offset 后产生的 0.02 mm 级小岛。
MIN_FEATURE_MM = 1.0

# STEP 黑色图案建模方式：
# contours_filtered：默认。按整体轮廓内缩并过滤小岛/薄壁碎片。
# rectangles_no_gaps：规则矩形模式，相邻黑色模块共享边不内缩，只在黑白交界处内缩。
# auto：普通 ArUco 字典使用 rectangles_no_gaps；DICT_APRILTAG_* 使用 contours_filtered。
STEP_GEOMETRY_MODE = "contours_filtered"

# STEP 输出形式：
# assembly：默认。白色基板和黑色图案作为多个实体/装配体导出，并保留黑白颜色。
# single_solid：将白色基板和黑色图案布尔融合为一个整体实体，适合在 SolidWorks 中作为单一零件处理。
STEP_EXPORT_MODE = "single_solid"

# PNG/SVG/DXF 分辨率：每个棋盘方格对应的像素数。
# 只影响 2D 文件精度，不影响 STEP 的真实尺寸。
PIXELS_PER_SQUARE = 240

# 默认输出哪些文件。命令行可用 --no-png / --no-svg / --no-dxf / --no-step 关闭。
GENERATE_PNG = True
GENERATE_SVG = True
GENERATE_DXF = True
GENERATE_STEP = True

# DXF 输出层。SolidWorks 建模推荐 black，白色直接用基板表示。
DXF_COLOR = "black"  # black / white / both


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate ChArUco calibration board PNG/SVG/DXF/STEP assets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--squares-x", type=int, default=SQUARES_X)
    parser.add_argument("--squares-y", type=int, default=SQUARES_Y)
    parser.add_argument("--square-mm", type=float, default=SQUARE_MM)
    parser.add_argument("--marker-mm", type=float, default=MARKER_MM)
    parser.add_argument("--dictionary", choices=sorted(core.ARUCO_DICTIONARIES), default=DICTIONARY)
    parser.add_argument("--base-width-mm", type=float, default=BASE_WIDTH_MM)
    parser.add_argument("--base-height-mm", type=float, default=BASE_HEIGHT_MM)
    parser.add_argument("--base-thickness-mm", type=float, default=BASE_THICKNESS_MM)
    parser.add_argument("--black-height-mm", type=float, default=BLACK_HEIGHT_MM)
    parser.add_argument("--black-shrink-mm", type=float, default=BLACK_SHRINK_MM)
    parser.add_argument("--min-feature-mm", type=float, default=MIN_FEATURE_MM)
    parser.add_argument(
        "--step-geometry-mode",
        choices=("auto", "rectangles_no_gaps", "contours_filtered"),
        default=STEP_GEOMETRY_MODE,
    )
    parser.add_argument("--step-export-mode", choices=("assembly", "single_solid"), default=STEP_EXPORT_MODE)
    parser.add_argument("--pixels-per-square", type=int, default=PIXELS_PER_SQUARE)
    parser.add_argument("--dxf-color", choices=("black", "white", "both"), default=DXF_COLOR)
    parser.add_argument("--no-png", action="store_true", default=not GENERATE_PNG)
    parser.add_argument("--no-svg", action="store_true", default=not GENERATE_SVG)
    parser.add_argument("--no-dxf", action="store_true", default=not GENERATE_DXF)
    parser.add_argument("--no-step", action="store_true", default=not GENERATE_STEP)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    args = core.make_args(
        board_type="charuco",
        output_dir=parsed.output_dir,
        output_prefix=parsed.output_prefix,
        squares_x=parsed.squares_x,
        squares_y=parsed.squares_y,
        square_mm=parsed.square_mm,
        marker_mm=parsed.marker_mm,
        dictionary=parsed.dictionary,
        base_width_mm=parsed.base_width_mm,
        base_height_mm=parsed.base_height_mm,
        base_thickness_mm=parsed.base_thickness_mm,
        black_height_mm=parsed.black_height_mm,
        black_shrink_mm=parsed.black_shrink_mm,
        min_feature_mm=parsed.min_feature_mm,
        black_geometry=parsed.step_geometry_mode,
        step_export_mode=parsed.step_export_mode,
        pixels_per_square=parsed.pixels_per_square,
        dxf_color=parsed.dxf_color,
        no_png=parsed.no_png,
        no_svg=parsed.no_svg,
        no_dxf=parsed.no_dxf,
        no_step=parsed.no_step,
    )
    return core.run_generation(args)


if __name__ == "__main__":
    raise SystemExit(main())
