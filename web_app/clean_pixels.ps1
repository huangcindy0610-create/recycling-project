
Add-Type -AssemblyName System.Drawing

function Clean-Image($filename) {
    $path = Join-Path (Get-Location) "static" $filename
    if (-not (Test-Path $path)) { echo "Not found: $path"; return }

    $img = [System.Drawing.Bitmap]::FromFile($path)
    $newImg = New-Object System.Drawing.Bitmap($img.Width, $img.Height)
    
    for ($x=0; $x -lt $img.Width; $x++) {
        for ($y=0; $y -lt $img.Height; $y++) {
            $c = $img.GetPixel($x, $y)
            
            # Condition: Is it Grey/White?
            # R=G=B (or close) AND Light (>200)
            $isGray = ([Math]::Abs($c.R - $c.G) -lt 10) -and ([Math]::Abs($c.G - $c.B) -lt 10) -and ([Math]::Abs($c.R - $c.B) -lt 10)
            $isLight = ($c.R -gt 200)
            
            if ($isGray -and $isLight) {
                # Transparent
                 $newImg.SetPixel($x, $y, [System.Drawing.Color]::Transparent)
            } else {
                 $newImg.SetPixel($x, $y, $c)
            }
        }
    }
    
    $temp = $path + ".tmp.png"
    $newImg.Save($temp)
    $img.Dispose()
    $newImg.Dispose()
    
    Remove-Item $path -Force
    Rename-Item $temp $path
    echo "Cleaned $filename"
}

Clean-Image "baby.png"
Clean-Image "cat_head.png"
Clean-Image "cat_tail.png"
