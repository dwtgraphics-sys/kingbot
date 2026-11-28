param([string]$Path)
# v271: like ocr_boxes.ps1 but one output line per WORD: x1|y1|x2|y2|lineIndex|word (game_login needs the
# 'Get Code' button apart from the code box it shares a text line with).
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
$i = 0
foreach ($line in $result.Lines) { foreach ($w in $line.Words) { $r = $w.BoundingRect; Write-Output ("{0}|{1}|{2}|{3}|{4}|{5}" -f [int]$r.X, [int]$r.Y, [int]($r.X + $r.Width), [int]($r.Y + $r.Height), $i, $w.Text) }; $i++ }
