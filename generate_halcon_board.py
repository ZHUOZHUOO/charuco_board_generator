#!/usr/bin/env python3
"""Generate a standard HALCON calibration plate.

This script mirrors HALCON gen_caltab() parameters, then exports matching
PNG/SVG/DXF/STEP assets for manufacturing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import board_generator_core as core


# ============================================================================
# 用户常改参数区：HALCON 标准标定板
# ----------------------------------------------------------------------------
# 参数命名对齐 HALCON gen_caltab():
# gen_caltab(XNum, YNum, MarkDist, DiameterRatio, CalPlateDescr, CalPlatePSFile)
#
# X_NUM / Y_NUM：X/Y 方向 MARK 圆点数量。
# MARK_DIST_M：相邻 MARK 圆心距离，单位是 m。
# DIAMETER_RATIO：MARK 直径 / MARK_DIST_M。
# CAL_PLATE_DESCR：HALCON 标定板描述文件，扩展名通常是 .descr。
# CAL_PLATE_PS_FILE：HALCON 标定板 PostScript 图像，扩展名通常是 .ps。
# ============================================================================

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_PREFIX = ""

X_NUM = 11
Y_NUM = 11
MARK_DIST_M = 0.02
DIAMETER_RATIO = 0.5
CAL_PLATE_DESCR = "halcon_board_11x11_20mm.descr"
CAL_PLATE_PS_FILE = "halcon_board_11x11_20mm.ps"

# STEP 中白色基板厚度。黑色图案会从基板顶面继续凸起。
BASE_THICKNESS_MM = 5.0

# 黑色图案凸起高度。STEP 总高度 = BASE_THICKNESS_MM + BLACK_HEIGHT_MM。
BLACK_HEIGHT_MM = 0.5

# 黑色圆点半径、外框边缘向内缩小量。用于给建模和 3D 打印留出少量裕量。
BLACK_SHRINK_MM = 0.02

# STEP 最小黑色特征尺寸。小于该值的黑色特征不会导出。
MIN_FEATURE_MM = 1.0

# STEP 黑色图案建模方式：
# contours_filtered：默认。按图像轮廓内缩并过滤小岛/薄壁碎片。
# rectangles_no_gaps：规则几何模式，圆点为圆柱，外框和三角标识为规则凸起。
STEP_GEOMETRY_MODE = "contours_filtered"

# STEP 输出形式：
# assembly：默认。白色基板和黑色图案作为多个实体/装配体导出，并保留黑白颜色。
# single_solid：将白色基板和黑色图案布尔融合为一个整体实体，适合在 SolidWorks 中作为单一零件处理。
STEP_EXPORT_MODE = "assembly"

# PNG/SVG/DXF 分辨率：每个圆心间距对应的像素数。
# 只影响 2D 文件精度，不影响 STEP 的真实尺寸。
PIXELS_PER_MARK_DIST = 240

GENERATE_PNG = True
GENERATE_SVG = True
GENERATE_DXF = True
GENERATE_STEP = True
GENERATE_DESCR = True
GENERATE_PS = True

# DXF 输出层。SolidWorks 建模推荐 black，白色直接用基板表示。
DXF_COLOR = "black"  # black / white / both


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a standard HALCON calibration plate.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--x-num", type=int, default=X_NUM)
    parser.add_argument("--y-num", type=int, default=Y_NUM)
    parser.add_argument("--mark-dist-m", type=float, default=MARK_DIST_M)
    parser.add_argument("--diameter-ratio", type=float, default=DIAMETER_RATIO)
    parser.add_argument("--cal-plate-descr", default=CAL_PLATE_DESCR)
    parser.add_argument("--cal-plate-ps-file", default=CAL_PLATE_PS_FILE)
    parser.add_argument("--base-thickness-mm", type=float, default=BASE_THICKNESS_MM)
    parser.add_argument("--black-height-mm", type=float, default=BLACK_HEIGHT_MM)
    parser.add_argument("--black-shrink-mm", type=float, default=BLACK_SHRINK_MM)
    parser.add_argument("--min-feature-mm", type=float, default=MIN_FEATURE_MM)
    parser.add_argument(
        "--step-geometry-mode",
        choices=("rectangles_no_gaps", "contours_filtered"),
        default=STEP_GEOMETRY_MODE,
    )
    parser.add_argument("--step-export-mode", choices=("assembly", "single_solid"), default=STEP_EXPORT_MODE)
    parser.add_argument("--pixels-per-mark-dist", type=int, default=PIXELS_PER_MARK_DIST)
    parser.add_argument("--dxf-color", choices=("black", "white", "both"), default=DXF_COLOR)
    parser.add_argument("--no-png", action="store_true", default=not GENERATE_PNG)
    parser.add_argument("--no-svg", action="store_true", default=not GENERATE_SVG)
    parser.add_argument("--no-dxf", action="store_true", default=not GENERATE_DXF)
    parser.add_argument("--no-step", action="store_true", default=not GENERATE_STEP)
    parser.add_argument("--no-descr", action="store_true", default=not GENERATE_DESCR)
    parser.add_argument("--no-ps", action="store_true", default=not GENERATE_PS)
    return parser


def build_core_args(parsed: argparse.Namespace) -> argparse.Namespace:
    if parsed.x_num <= 1 or parsed.y_num <= 1:
        raise ValueError("X_NUM 和 Y_NUM 都必须大于 1。")
    if parsed.mark_dist_m <= 0.0:
        raise ValueError("MARK_DIST_M 必须为正数。")
    if not 0.0 < parsed.diameter_ratio < 1.0:
        raise ValueError("DIAMETER_RATIO 必须满足 0 < DIAMETER_RATIO < 1。")

    mark_dist_mm = parsed.mark_dist_m * 1000.0
    circle_diameter_mm = mark_dist_mm * parsed.diameter_ratio

    # HALCON gen_caltab() 的标准矩形标定板几何：
    # 黑色外框外边界尺寸 = (XNum + 1) * MarkDist by (YNum + 1) * MarkDist。
    # 标定板白色外轮廓在黑框外再留 MarkDist / 10 的边。
    # 黑框线宽 = MarkDist / 4。
    rim_mm = mark_dist_mm / 10.0
    frame_width_mm = mark_dist_mm / 4.0
    board_width_mm = (parsed.x_num + 1) * mark_dist_mm + 2.0 * rim_mm
    board_height_mm = (parsed.y_num + 1) * mark_dist_mm + 2.0 * rim_mm

    output_prefix = parsed.output_prefix
    if not output_prefix:
        output_prefix = (
            f"halcon_board_{core.fmt_token(board_width_mm)}x{core.fmt_token(board_height_mm)}_"
            f"{parsed.x_num}x{parsed.y_num}_"
            f"dist{core.fmt_token(mark_dist_mm)}mm_"
            f"ratio{core.fmt_token(parsed.diameter_ratio)}"
        )

    return core.make_args(
        board_type="framed_circle_grid",
        output_dir=parsed.output_dir,
        output_prefix=output_prefix,
        circles_x=parsed.x_num,
        circles_y=parsed.y_num,
        circle_spacing_mm=mark_dist_mm,
        circle_diameter_mm=circle_diameter_mm,
        frame_margin_mm=rim_mm,
        frame_width_mm=frame_width_mm,
        triangle_enabled=True,
        triangle_base_mm=mark_dist_mm,
        triangle_height_mm=mark_dist_mm,
        triangle_edge_gap_mm=0.0,
        base_width_mm=board_width_mm,
        base_height_mm=board_height_mm,
        base_thickness_mm=parsed.base_thickness_mm,
        black_height_mm=parsed.black_height_mm,
        black_shrink_mm=parsed.black_shrink_mm,
        min_feature_mm=parsed.min_feature_mm,
        black_geometry=parsed.step_geometry_mode,
        step_export_mode=parsed.step_export_mode,
        pixels_per_square=parsed.pixels_per_mark_dist,
        dxf_color=parsed.dxf_color,
        no_png=parsed.no_png,
        no_svg=parsed.no_svg,
        no_dxf=parsed.no_dxf,
        no_step=parsed.no_step,
    )


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    try:
        args = build_core_args(parsed)
    except ValueError as exc:
        print(f"[ERROR] 参数无效：{exc}", file=sys.stderr)
        return 2
    result = core.run_generation(args)
    if result != 0:
        return result

    if not parsed.no_descr:
        descr_path = core.write_halcon_descr(args.resolved_output_dir, args, parsed.cal_plate_descr)
        print(f"[SUCCESS] HALCON descr: {descr_path}")
    if not parsed.no_ps:
        ps_path = core.write_halcon_ps(args.resolved_output_dir, args, parsed.cal_plate_ps_file)
        print(f"[SUCCESS] HALCON PS: {ps_path}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
