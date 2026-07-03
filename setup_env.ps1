$ErrorActionPreference = "Stop"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 conda。请先安装 Miniconda 或 Anaconda，并确保 conda 已加入 PATH。"
}

Push-Location $PSScriptRoot
try {
    $envExists = conda env list | Select-String -Pattern "charuco-board-generator"
    if ($envExists) {
        Write-Host "[INFO] Updating conda environment: charuco-board-generator"
        conda env update -f environment.yml --prune
    } else {
        Write-Host "[INFO] Creating conda environment: charuco-board-generator"
        conda env create -f environment.yml
    }

    Write-Host ""
    Write-Host "[SUCCESS] Environment is ready."
    Write-Host "Run:"
    Write-Host "  conda activate charuco-board-generator"
    Write-Host "  python generate_charuco_board.py"
    Write-Host "  python generate_chess_board.py"
    Write-Host "  python generate_circle_grid_board.py"
    Write-Host "  python generate_asymmetric_circle_grid_board.py"
    Write-Host "  python generate_aruco_marker_board.py"
    Write-Host "  python generate_halcon_board.py"
} finally {
    Pop-Location
}
