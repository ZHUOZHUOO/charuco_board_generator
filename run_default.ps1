param(
    [ValidateSet("charuco", "chess", "circle", "asym_circle", "aruco", "aprilgrid", "halcon")]
    [string]$Board = "charuco"
)

$ErrorActionPreference = "Stop"

$scripts = @{
    charuco     = "generate_charuco_board.py"
    chess       = "generate_chess_board.py"
    circle      = "generate_circle_grid_board.py"
    asym_circle = "generate_asymmetric_circle_grid_board.py"
    aruco       = "generate_aruco_marker_board.py"
    aprilgrid   = "generate_aprilgrid_board.py"
    halcon      = "generate_halcon_board.py"
}

Push-Location $PSScriptRoot
try {
    $script = $scripts[$Board]
    conda run -n calibration-target-generator python $script
} finally {
    Pop-Location
}
