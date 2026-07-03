#!/usr/bin/env python3
"""Generate an Aprilgrid calibration target."""

from __future__ import annotations

import argparse
from pathlib import Path

import board_generator_core as core


# ============================================================================
# 用户常改参数区：Aprilgrid 标定板
# ----------------------------------------------------------------------------
# 所有尺寸单位都是 mm；STEP/DXF 也都以 mm 为单位。
# 参数命名对齐 Kalibr Aprilgrid 常用配置：
#   TAG_COLS / TAG_ROWS：横向/纵向 AprilTag 数量
#   TAG_SIZE_MM：单个 AprilTag 边长
#   TAG_SPACING_RATIO：相邻 tag 白色间距 / TAG_SIZE_MM
# 脚本会额外生成 Kalibr 可用的 aprilgrid YAML 配置文件。
# ============================================================================

# 输出目录：所有生成文件默认写到这里。
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"

# 输出文件名前缀。留空时脚本会根据尺寸自动生成。
OUTPUT_PREFIX = ""

# AprilTag 排列数量。COLS 是横向 tag 数，ROWS 是纵向 tag 数。
TAG_COLS = 6
TAG_ROWS = 6

# 单个 AprilTag 的实体边长。Kalibr YAML 中会换算为米。
TAG_SIZE_MM = 20.0

# 相邻 tag 的白色间距比例。实际间距 = TAG_SIZE_MM * TAG_SPACING_RATIO。
TAG_SPACING_RATIO = 0.3

# 起始 tag id。脚本会按行优先顺序连续使用 id。
FIRST_TAG_ID = 0

# AprilTag 黑色边框位数。Kalibr Aprilgrid 使用 2-bit black border。
BORDER_BITS = 2

# AprilTag 字典。Kalibr 常见 Aprilgrid 多使用 36h11。
DICTIONARY = "DICT_APRILTAG_36H11"

# 白色基板外形尺寸。
# 默认：包含角点黑色方块后的图案区域 162 x 162 mm，基板 180 x 180 mm，四周留白 9 mm。
BASE_WIDTH_MM = 180.0
BASE_HEIGHT_MM = 180.0

# 白色基板厚度。STEP 中白色基板从 Z=0 拉伸到该高度。
BASE_THICKNESS_MM = 5.0

# 黑色图案凸起高度。STEP 总高度 = BASE_THICKNESS_MM + BLACK_HEIGHT_MM。
BLACK_HEIGHT_MM = 0.5

# 黑色轮廓向内缩小量。用于避免黑白区域角点相切导致薄壁/零厚度问题。
BLACK_SHRINK_MM = 0.02

# STEP 最小黑色特征尺寸。任一边小于该值的小黑块不会导出。
MIN_FEATURE_MM = 1.0

# STEP 黑色图案建模方式：
# rectangles_no_gaps：推荐。相邻黑色单元共享边不内缩，只在黑白交界处内缩。
# contours_filtered：按整体轮廓内缩并过滤小岛/薄壁碎片。
STEP_GEOMETRY_MODE = "rectangles_no_gaps"

# PNG/SVG/DXF 分辨率：每个 tag 边长对应的像素数。
# 只影响 2D 文件精度，不影响 STEP 的真实尺寸。
PIXELS_PER_TAG = 240

# 默认输出哪些文件。命令行可用 --no-png / --no-svg / --no-dxf / --no-step / --no-yaml 关闭。
GENERATE_PNG = True
GENERATE_SVG = True
GENERATE_DXF = True
GENERATE_STEP = True
GENERATE_YAML = True

# DXF 输出层。SolidWorks 建模推荐 black，白色直接用基板表示。
DXF_COLOR = "black"  # black / white / both


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Aprilgrid calibration target PNG/SVG/DXF/STEP/YAML assets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--tag-cols", type=int, default=TAG_COLS)
    parser.add_argument("--tag-rows", type=int, default=TAG_ROWS)
    parser.add_argument("--tag-size-mm", type=float, default=TAG_SIZE_MM)
    parser.add_argument("--tag-spacing-ratio", type=float, default=TAG_SPACING_RATIO)
    parser.add_argument("--first-tag-id", type=int, default=FIRST_TAG_ID)
    parser.add_argument("--border-bits", type=int, default=BORDER_BITS)
    parser.add_argument("--dictionary", choices=sorted(core.APRILTAG_DICTIONARIES), default=DICTIONARY)
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
    parser.add_argument("--pixels-per-tag", type=int, default=PIXELS_PER_TAG)
    parser.add_argument("--dxf-color", choices=("black", "white", "both"), default=DXF_COLOR)
    parser.add_argument("--aprilgrid-yaml-file", default="")
    parser.add_argument("--no-png", action="store_true", default=not GENERATE_PNG)
    parser.add_argument("--no-svg", action="store_true", default=not GENERATE_SVG)
    parser.add_argument("--no-dxf", action="store_true", default=not GENERATE_DXF)
    parser.add_argument("--no-step", action="store_true", default=not GENERATE_STEP)
    parser.add_argument("--no-yaml", action="store_true", default=not GENERATE_YAML)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    marker_gap_mm = parsed.tag_size_mm * parsed.tag_spacing_ratio
    args = core.make_args(
        board_type="aprilgrid",
        output_dir=parsed.output_dir,
        output_prefix=parsed.output_prefix,
        markers_x=parsed.tag_cols,
        markers_y=parsed.tag_rows,
        aruco_marker_mm=parsed.tag_size_mm,
        marker_gap_mm=marker_gap_mm,
        tag_spacing_ratio=parsed.tag_spacing_ratio,
        marker_border_bits=parsed.border_bits,
        first_marker_id=parsed.first_tag_id,
        dictionary=parsed.dictionary,
        base_width_mm=parsed.base_width_mm,
        base_height_mm=parsed.base_height_mm,
        base_thickness_mm=parsed.base_thickness_mm,
        black_height_mm=parsed.black_height_mm,
        black_shrink_mm=parsed.black_shrink_mm,
        min_feature_mm=parsed.min_feature_mm,
        black_geometry=parsed.step_geometry_mode,
        pixels_per_square=parsed.pixels_per_tag,
        dxf_color=parsed.dxf_color,
        no_png=parsed.no_png,
        no_svg=parsed.no_svg,
        no_dxf=parsed.no_dxf,
        no_step=parsed.no_step,
    )
    result = core.run_generation(args)
    if result != 0:
        return result

    if not parsed.no_yaml:
        yaml_file = parsed.aprilgrid_yaml_file or f"{core.default_prefix(args)}.yaml"
        yaml_path = core.write_aprilgrid_yaml(args.output_dir, args, yaml_file)
        print(f"[SUCCESS] Aprilgrid YAML: {yaml_path}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
