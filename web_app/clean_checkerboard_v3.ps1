
Add-Type -AssemblyName System.Drawing

function Remove-Checkerboard($filename) {
    # Nested Join-Path for compatibility
    $dir = Join-Path (Get-Location) "static"
    $path = Join-Path $dir $filename
    
    if (-not (Test-Path $path)) {
        Write-Host "File not found: $path"
        return
    }
    
    echo "Processing: $filename"
    try {
        $img = [System.Drawing.Bitmap]::FromFile($path)
        $newImg = New-Object System.Drawing.Bitmap($img.Width, $img.Height)
        $g = [System.Drawing.Graphics]::FromImage($newImg)
        $g.DrawImage($img, 0, 0, $img.Width, $img.Height)
        
        # Transparent removal
        $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 255, 255, 255))
        $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 204, 204, 204)) 
        
        $newPath = $path + ".temp.png"
        $newImg.Save($newPath, [System.Drawing.Imaging.ImageFormat]::Png)
        
        $g.Dispose()
        $img.Dispose()
        $newImg.Dispose()
        
        # Force overwrite
        Move-Item -Path $newPath -Destination $path -Force
        Write-Host "Done: $filename"
    } catch {
        Write-Host "FATAL ERROR processing $filename : $_"
    }
}

Remove-Checkerboard "baby.png"
Remove-Checkerboard "cat_head.png"
Remove-Checkerboard "cat_tail.png"
