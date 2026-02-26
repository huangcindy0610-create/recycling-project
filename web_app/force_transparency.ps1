
Add-Type -AssemblyName System.Drawing

function MakeTransparent($path) {
    if (-not (Test-Path $path)) {
        Write-Host "File not found: $path"
        return
    }
    
    echo "Processing for Transparency: $path"
    $img = [System.Drawing.Bitmap]::FromFile($path)
    
    # Create new bitmap
    $newImg = New-Object System.Drawing.Bitmap($img.Width, $img.Height)
    $g = [System.Drawing.Graphics]::FromImage($newImg)
    $g.DrawImage($img, 0, 0, $img.Width, $img.Height)
    
    # Simple White to Transparent
    $newImg.MakeTransparent([System.Drawing.Color]::White)
    
    # Save temp
    $newPath = $path + ".trans.png"
    $newImg.Save($newPath, [System.Drawing.Imaging.ImageFormat]::Png)
    
    $g.Dispose()
    $img.Dispose()
    $newImg.Dispose()
    
    # Replace
    Remove-Item $path
    Rename-Item $newPath $path
}

$base = "c:\Users\huang\OneDrive\桌面\資處科專題\web_app\static"
MakeTransparent "$base\baby.png"
MakeTransparent "$base\cat_head.png"
MakeTransparent "$base\cat_tail.png"
MakeTransparent "$base\cat_parts.png"
