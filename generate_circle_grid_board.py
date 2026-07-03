#!/usr/bin/env python3
"""Generate a symmetric circle-grid calibration board."""

from __future__ import annotations

import argparse
from pathlib import Path

import board_generator_core as core


# ============================================================================
# 用户常改参数区：对称圆点阵列标定板
# ----------------------------------------------------------------------------
# 所有尺寸单位都是 mm；STEP/DXF 也都以 mm 为单位。
# 临时修改参数时，也可以使用命令行参数覆盖下面的默认值。
# ============================================================================

# 输出目录：所有生成文件默认写到这里。
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"

# 输出文件名前缀。留空时脚本会根据尺寸自动生成。
OUTPUT_PREFIX = ""

# 圆点数量。X 是横向圆点数，Y 是纵向圆点数。
CIRCLES_X = 11
CIRCLES_Y = 8

# 相邻圆心距离。相机标定时也要使用这个真实尺寸。
CIRCLE_SPACING_MM = 20.0

# 圆点直径。建议小于 CIRCLE_SPACING_MM，避免圆点相连。
CIRCLE_DIAMETER_MM = 8.0

# 白色基板外形尺寸。
# 默认：圆点区域 208 x 148 mm，基板 240 x 180 mm，四周留白约 16 mm。
BASE_WIDTH_MM = 240.0
BASE_HEIGHT_MM = 180.0

# 白色基板厚度。STEP 中白色基板从 Z=0 拉伸到该高度。
BASE_THICKNESS_MM = 5.0

# 黑色圆点凸起高度。STEP 总高度 = BASE_THICKNESS_MM + BLACK_HEIGHT_MM。
BLACK_HEIGHT_MM = 0.5

# 黑色圆点半径向内缩小量。用于给 3D 打印和建模留出少量裕量。
BLACK_SHRINK_MM = 0.02

# STEP 最小黑色特征尺寸。圆点直径扣除内缩后小于该值时不会导出。
MIN_FEATURE_MM = 1.0

# STEP 黑色图案建模方式：
# rectangles_no_gaps：推荐。圆点板在该模式下会生成真实圆柱。
# contours_filtered：按图像轮廓生成实体，主要用于对比，不建议优先使用。
STEP_GEOMETRY_MODE = "rectangles_no_gaps"

# PNG/SVG/DXF 分辨率：每个圆心间距对应的像素数。
# 只影响 2D 文件精度，不影响 STEP 的真实尺寸。
PIXELS_PER_SPACING = 240

# 默认输出哪些文件。命令行可用 --no-png / --no-svg / --no-dxf / --no-step 关闭。
GENERATE_PNG = True
GENERATE_SVG = True
GENERATE_DXF = True
GENERATE_STEP = True

# DXF 输出层。SolidWorks 建模推荐 black，白色直接用基板表示。
DXF_COLOR = "black"  # black / white / both


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate circle-grid calibration board PNG/SVG/DXF/STEP assets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--circles-x", type=int, default=CIRCLES_X)
    parser.add_argument("--circles-y", type=int, default=CIRCLES_Y)
    parser.add_argument("--circle-spacing-mm", type=float, default=CIRCLE_SPACING_MM)
    parser.add_argument("--circle-diameter-mm", type=float, default=CIRCLE_DIAMETER_MM)
    parser.add_argument("--base-width-mm", type=float, default=BASE_WIDTH_MM)
    parser.add_argument("--base-height-mm", type=float, default=BASE_HEIGHT_MM)
    parser.add_argument("--base-thickness-mm", type=float, default=BASE_THICKNESS_MM)
    parser.add_argument("--black-height-mm", type=float, default=BLACK_HEIGHT_MM)
    parser.add_argument("--black-shrink-mm", type=float, default=BLACK_SHRINK_MM)
    parser.add_argument("--min-feature-mm", type=float, default=MIN_FEATURE_MM)
    parser.add_argument(
        "--step-geometry-mode",
        choices=("rectangles_no_gaps", "contours_filtered"),
        default=STEP_GEOMETRY_MODE,
    )
    parser.add_argument("--pixels-per-spacing", type=int, default=PIXELS_PER_SPACING)
    parser.add_argument("--dxf-color", choices=("black", "white", "both"), default=DXF_COLOR)
    parser.add_argument("--no-png", action="store_true", default=not GENERATE_PNG)
    parser.add_argument("--no-svg", action="store_true", default=not GENERATE_SVG)
    parser.add_argument("--no-dxf", action="store_true", default=not GENERATE_DXF)
    parser.add_argument("--no-step", action="store_true", default=not GENERATE_STEP)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    args = core.make_args(
        board_type="circle_grid",
        output_dir=parsed.output_dir,
        output_prefix=parsed.output_prefix,
        circles_x=parsed.circles_x,
        circles_y=parsed.circles_y,
        circle_spacing_mm=parsed.circle_spacing_mm,
        circle_diameter_mm=parsed.circle_diameter_mm,
        base_width_mm=parsed.base_width_mm,
        base_height_mm=parsed.base_height_mm,
        base_thickness_mm=parsed.base_thickness_mm,
        black_height_mm=parsed.black_height_mm,
        black_shrink_mm=parsed.black_shrink_mm,
        min_feature_mm=parsed.min_feature_mm,
        black_geometry=parsed.step_geometry_mode,
        pixels_per_square=parsed.pixels_per_spacing,
        dxf_color=parsed.dxf_color,
        no_png=parsed.no_png,
        no_svg=parsed.no_svg,
        no_dxf=parsed.no_dxf,
        no_step=parsed.no_step,
    )
    return core.run_generation(args)


if __name__ == "__main__":
    raise SystemExit(main())
