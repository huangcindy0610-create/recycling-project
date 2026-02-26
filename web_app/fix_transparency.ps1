
Add-Type -AssemblyName System.Drawing

function MakeTransparent($path) {
    echo "Processing $path"
    $img = [System.Drawing.Bitmap]::FromFile($path)
    $img.MakeTransparent([System.Drawing.Color]::White)
    
    # Save to a new file to avoid locking issues, then replace
    $newPath = $path + ".temp.png"
    $img.Save($newPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $img.Dispose()
    
    Remove-Item $path
    Rename-Item $newPath $path
}

$base = "c:\Users\huang\OneDrive\桌面\資處科專題\web_app\static"
MakeTransparent "$base\baby.png"
MakeTransparent "$base\cat_parts.png"
