param(
    [ValidateSet("charuco", "chess", "circle", "halcon")]
    [string]$Board = "charuco"
)

$ErrorActionPreference = "Stop"

$scripts = @{
    charuco = "generate_charuco_board.py"
    chess   = "generate_chess_board.py"
    circle  = "generate_circle_grid_board.py"
    halcon  = "generate_halcon_board.py"
}

Push-Location $PSScriptRoot
try {
    $script = $scripts[$Board]
    conda run -n charuco-board-generator python $script
} finally {
    Pop-Location
}
