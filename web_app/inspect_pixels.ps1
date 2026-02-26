
Add-Type -AssemblyName System.Drawing

function Inspect-Pixel($path, $x, $y) {
    if (-not (Test-Path $path)) {
        Write-Host "File not found: $path"
        return
    }
    
    $img = [System.Drawing.Bitmap]::FromFile($path)
    $color = $img.GetPixel($x, $y)
    Write-Host "Pixel at ($x,$y) in $path : R=$($color.R) G=$($color.G) B=$($color.B) A=$($color.A)"
    $img.Dispose()
}

$base = "c:\Users\huang\OneDrive\桌面\資處科專題\web_app\static"
# Inspect corners where checkerboard usually is
Inspect-Pixel "$base\baby.png" 0 0
Inspect-Pixel "$base\baby.png" 20 0
Inspect-Pixel "$base\baby.png" 0 20
