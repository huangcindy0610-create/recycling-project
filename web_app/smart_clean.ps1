
$code = @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public class ImageCleaner {
    public static void Clean(string path) {
        if (!System.IO.File.Exists(path)) {
            Console.WriteLine("File not found: " + path);
            return;
        }

        Console.WriteLine("Cleaning: " + path);
        Bitmap bmp = new Bitmap(path);
        
        // Lock bits for speed
        BitmapData data = bmp.LockBits(new Rectangle(0, 0, bmp.Width, bmp.Height), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
        int bytes = Math.Abs(data.Stride) * bmp.Height;
        byte[] rgbValues = new byte[bytes];
        Marshal.Copy(data.Scan0, rgbValues, 0, bytes);

        for (int i = 0; i < rgbValues.Length; i += 4) {
            byte b = rgbValues[i];
            byte g = rgbValues[i + 1];
            byte r = rgbValues[i + 2];
            // alpha is i+3

            // Check for Neutral Light Colors (White/Gray/Off-White)
            // Threshold: Brightness > 200, Saturation low (RGB close to each other)
            if (r > 210 && g > 210 && b > 210) {
                if (Math.Abs(r - g) < 15 && Math.Abs(g - b) < 15 && Math.Abs(r - b) < 15) {
                    // Set Alpha to 0
                    rgbValues[i + 3] = 0;
                }
            }
        }

        Marshal.Copy(rgbValues, 0, data.Scan0, bytes);
        bmp.UnlockBits(data);

        string temp = path + ".fix.png";
        bmp.Save(temp, ImageFormat.Png);
        bmp.Dispose();
        
        // Replace
        System.IO.File.Delete(path);
        System.IO.File.Move(temp, path);
        Console.WriteLine("Context: Cleaned " + path);
    }
}
"@

Add-Type -TypeDefinition $code -ReferencedAssemblies System.Drawing

function Do-Clean($filename) {
    $dir = Join-Path (Get-Location) "static"
    $path = Join-Path $dir $filename
    [ImageCleaner]::Clean($path)
}

Do-Clean "baby.png"
Do-Clean "cat_head.png"
Do-Clean "cat_tail.png"
