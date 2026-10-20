# Sets the board's time of day (the clock, gamehost/walltime.py) to this computer's, over the USB serial console,
# and prints the board's reply. Close any serial monitor on the port first (only one program can have it open).
#   powershell -ExecutionPolicy Bypass -File tools\settime.ps1 COM16
param([Parameter(Mandatory = $true)][string]$Port)
$p = New-Object System.IO.Ports.SerialPort $Port, 115200
$p.DtrEnable = $true
$p.Open()
try {
    Start-Sleep -Milliseconds 300
    $p.ReadExisting() | Out-Null
    # wait for the start of a second, so the board starts its milliseconds close to the computer's
    while ((Get-Date).Millisecond -gt 20) { Start-Sleep -Milliseconds 1 }
    $p.Write("/time " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "`r")
    $reply = ""
    $end = (Get-Date).AddSeconds(3)
    while ((Get-Date) -lt $end -and $reply -notmatch "Set: .*\.|No command|Type the time") {
        Start-Sleep -Milliseconds 50
        $reply += $p.ReadExisting()
    }
    if ($reply -match "(Set: .*\.)|(No command.*)|(Type the time.*)") { $Matches[0] } else { "No reply: is the clock running on the board?" }
} finally {
    $p.Close()
}
