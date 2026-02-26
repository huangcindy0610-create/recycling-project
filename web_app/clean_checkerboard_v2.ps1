
Add-Type -AssemblyName System.Drawing

function Remove-Checkerboard($filename) {
    # Use current location
    $path = Join-Path (Get-Location) "static" $filename
    
    if (-not (Test-Path $path)) {
        Write-Host "File not found: $path"
        return
    }
    
    echo "Cleaning Checkerboard from: $path"
    try {
        $img = [System.Drawing.Bitmap]::FromFile($path)
        $newImg = New-Object System.Drawing.Bitmap($img.Width, $img.Height)
        $g = [System.Drawing.Graphics]::FromImage($newImg)
        $g.DrawImage($img, 0, 0, $img.Width, $img.Height)
        
        # Checkerboard Colors
        # Standard Transparent Grid usually gray/white
        $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 255, 255, 255))
        $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 204, 204, 204)) 
        
        # Save
        $newPath = $path + ".clean.png"
        $newImg.Save($newPath, [System.Drawing.Imaging.ImageFormat]::Png)
        
        $g.Dispose()
        $img.Dispose()
        $newImg.Dispose()
        
        Remove-Item $path -Force
        Rename-Item $newPath $path -Force
        Write-Host "Success: $filename"
    } catch {
        Write-Host "Error processing $filename : $_"
    }
}

Remove-Checkerboard "baby.png"
Remove-Checkerboard "cat_head.png"
Remove-Checkerboard "cat_tail.png"
