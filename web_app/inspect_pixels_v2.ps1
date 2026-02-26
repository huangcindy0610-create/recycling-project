
Add-Type -AssemblyName System.Drawing

function Inspect-Pixel($filename, $x, $y) {
    $dir = Join-Path (Get-Location) "static"
    $path = Join-Path $dir $filename

    if (-not (Test-Path $path)) {
        Write-Host "File not found: $path"
        return
    }
    
    $img = [System.Drawing.Bitmap]::FromFile($path)
    $color = $img.GetPixel($x, $y)
    Write-Host "Pixel at ($x,$y) in $filename : R=$($color.R) G=$($color.G) B=$($color.B) A=$($color.A)"
    $img.Dispose()
}

Inspect-Pixel "baby.png" 0 0
Inspect-Pixel "baby.png" 10 10 # Diagonal might hit other square
Inspect-Pixel "baby.png" 0 20  # Vertical might hit other square
Inspect-Pixel "baby.png" 20 0  # Horizontal
