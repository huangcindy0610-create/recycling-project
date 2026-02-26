
Add-Type -AssemblyName System.Drawing

function Remove-Checkerboard($path) {
    if (-not (Test-Path $path)) {
        Write-Host "File not found: $path"
        return
    }
    
    echo "Cleaning Checkerboard from: $path"
    $img = [System.Drawing.Bitmap]::FromFile($path)
    $newImg = New-Object System.Drawing.Bitmap($img.Width, $img.Height)
    $g = [System.Drawing.Graphics]::FromImage($newImg)
    $g.DrawImage($img, 0, 0, $img.Width, $img.Height)
    
    # Common Checkerboard Colors
    # White
    $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 255, 255, 255))
    # Light Grays often used in checkerboards
    $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 204, 204, 204)) 
    $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 238, 238, 238)) 
    $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 252, 252, 252))
    $newImg.MakeTransparent([System.Drawing.Color]::FromArgb(255, 192, 192, 192))
    
    # Save
    $newPath = $path + ".clean.png"
    $newImg.Save($newPath, [System.Drawing.Imaging.ImageFormat]::Png)
    
    $g.Dispose()
    $img.Dispose()
    $newImg.Dispose()
    
    Remove-Item $path
    Rename-Item $newPath $path
}

$base = "c:\Users\huang\OneDrive\桌面\資處科專題\web_app\static"
Remove-Checkerboard "$base\baby.png"
Remove-Checkerboard "$base\cat_head.png"
Remove-Checkerboard "$base\cat_tail.png"
