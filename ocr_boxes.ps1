param([string]$Path)
# Windows built-in OCR (Windows.Media.Ocr). Prints the recognised text, one line per text line.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) {
    $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}
# v335: English first - the game text is English. With an Arabic (or other) Windows profile language the
# engine read digits but no English words (vps-04-c001: "ocr_boxes: nothing" while resources were read).
$engine = $null
# v344: any installed English recogniser (en-US / en-GB / en-...) - an en-GB-only server got NO_EN_OCR with en-US
try { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language "en-US")) } catch {}
if ($null -eq $engine) {
    try {
        foreach ($lg in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) {
            if ($lg.LanguageTag -like "en*") { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lg); if ($null -ne $engine) { break } }
        }
    } catch {}
}
if ($null -eq $engine) {
    [Console]::Error.WriteLine("NO_EN_OCR")
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) { Write-Output "NO_OCR_ENGINE"; exit 2 }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
foreach ($line in $result.Lines) { $x1 = 99999; $y1 = 99999; $x2 = 0; $y2 = 0; foreach ($w in $line.Words) { $r = $w.BoundingRect; if ($r.X -lt $x1) { $x1 = $r.X }; if ($r.Y -lt $y1) { $y1 = $r.Y }; if ($r.X + $r.Width -gt $x2) { $x2 = $r.X + $r.Width }; if ($r.Y + $r.Height -gt $y2) { $y2 = $r.Y + $r.Height } }; Write-Output ("{0}|{1}|{2}|{3}|{4}" -f [int]$x1, [int]$y1, [int]$x2, [int]$y2, $line.Text) }
