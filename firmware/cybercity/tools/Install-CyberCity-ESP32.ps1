#Requires -Version 5.1
<#
Cyber City ESP32 guided installer for Windows PowerShell 5.1 / PowerShell 7.
Run from the extracted Basic ESP32 Firmware ZIP by double-clicking
Install-CyberCity-ESP32.cmd. Flash MicroPython first with Thonny.
Does not erase the board or enable OTA. Offers optional, explicit autostart
by creating main.py only if the board has no existing main.py.
#>
[CmdletBinding()]
param(
    [string]$FirmwareDirectory = '',
    [string]$Port = '',
    [string]$PythonPath = '',
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ApplicationFiles = @(
    'device_startup.py', 'labtech_https.py', 'mqtt_controller.py',
    'command_protocol.py', 'secure_stage.py', 'ota_staging.py',
    'ota_activation.py', 'ota_supervisor_preview.py', 'ota_single_app.py',
    'ota_polling.py', 'ota_restart.py', 'firmware_report.py',
    'health_observer.py', 'onboard_check.py'
)
$OptionalFiles = @(
    'mqtt_tls_config.py', 'ota_runtime_config.py', 'labtech-ca.der'
)

function Confirm-Answer([string]$Question, [bool]$DefaultYes = $true) {
    $hint = if ($DefaultYes) { 'Y/n' } else { 'y/N' }
    while ($true) {
        $answer = (Read-Host "$Question [$hint]").Trim().ToLowerInvariant()
        if (-not $answer) { return $DefaultYes }
        if ($answer -in @('y', 'yes')) { return $true }
        if ($answer -in @('n', 'no')) { return $false }
        Write-Host 'Enter Y or N.' -ForegroundColor Yellow
    }
}

function Prompt-Value([string]$Question, [string]$Default = '') {
    while ($true) {
        $label = if ($Default) { "$Question [$Default]" } else { $Question }
        $answer = Read-Host $label
        if ([string]::IsNullOrWhiteSpace($answer)) { $answer = $Default }
        if (-not [string]::IsNullOrWhiteSpace($answer)) { return $answer.Trim() }
        Write-Host 'A value is required.' -ForegroundColor Yellow
    }
}

function Prompt-Secret([string]$Question) {
    while ($true) {
        $secure = Read-Host $Question -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
        if ($value) { return $value }
        Write-Host 'A nonempty value is required.' -ForegroundColor Yellow
    }
}

function To-PythonString([string]$Value) {
    # Escape special characters without passing secrets on a command line.
    $out = [System.Text.StringBuilder]::new()
    [void]$out.Append('"')
    foreach ($char in $Value.ToCharArray()) {
        $n = [int][char]$char
        if ($n -eq 34) { [void]$out.Append('\"') }
        elseif ($n -eq 92) { [void]$out.Append('\\') }
        elseif ($n -eq 10) { [void]$out.Append('\n') }
        elseif ($n -eq 13) { [void]$out.Append('\r') }
        elseif ($n -eq 9) { [void]$out.Append('\t') }
        elseif ($n -lt 32 -or $n -eq 127) {
            [void]$out.Append('\u' + $n.ToString('x4'))
        } else { [void]$out.Append($char) }
    }
    [void]$out.Append('"')
    return $out.ToString()
}

function Write-Config([string]$FileName, [string[]]$Lines) {
    $target = Join-Path $FirmwareDirectory $FileName
    $value = ($Lines -join [Environment]::NewLine) + [Environment]::NewLine
    # PowerShell 5.1's "UTF8" encoding adds a BOM, which MicroPython may reject.
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($target, $value, $utf8)
    Write-Host "Saved $FileName (contains credentials; keep this folder private)."
}

function Test-Python([string]$Candidate) {
    if (-not $Candidate) { return $false }
    try {
        $probe = & $Candidate -c 'import sys; print(sys.version_info[0])' 2>$null
        return ($LASTEXITCODE -eq 0 -and (@($probe) -join '').Trim() -eq '3')
    } catch {
        return $false
    }
}

function Find-Python([string]$Explicit = '') {
    if ($Explicit) {
        if (-not (Test-Python $Explicit)) {
            throw "The specified Python executable is not usable: $Explicit"
        }
        return $Explicit
    }
    $candidates = [System.Collections.Generic.List[string]]::new()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $viaLauncher = & py -3 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $candidates.Add(($viaLauncher | Select-Object -Last 1).Trim()) }
        } catch { }
    }
    foreach ($cmd in @(Get-Command python -All -ErrorAction SilentlyContinue)) {
        if ($cmd.Source) { $candidates.Add($cmd.Source) }
    }
    if ($env:LOCALAPPDATA) {
        $core = Join-Path $env:LOCALAPPDATA 'Python'
        if (Test-Path $core) {
            foreach ($folder in @(Get-ChildItem $core -Directory -Filter 'pythoncore-*' -ErrorAction SilentlyContinue)) {
                $candidates.Add((Join-Path $folder.FullName 'python.exe'))
            }
        }
        $programs = Join-Path $env:LOCALAPPDATA 'Programs\Python'
        if (Test-Path $programs) {
            foreach ($folder in @(Get-ChildItem $programs -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue)) {
                $candidates.Add((Join-Path $folder.FullName 'python.exe'))
            }
        }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Python $candidate) { return $candidate }
    }
    return $null
}

function Ensure-Python() {
    $python = Find-Python $PythonPath
    if ($python) { return $python }
    Write-Host 'Python 3 was not found.' -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Install Python 3 from https://www.python.org/downloads/windows/ and rerun the installer.'
    }
    if (-not (Confirm-Answer 'Install Python 3.13 using Windows Package Manager (winget)?')) {
        throw 'Python 3 is required. No changes were made to the ESP32.'
    }
    & winget install --id Python.Python.3.13 --exact --source winget --scope user --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed; install Python manually and rerun.' }
    $python = Find-Python
    if (-not $python) {
        throw 'Python was installed but is not yet visible. Reopen PowerShell and run the installer again.'
    }
    return $python
}

function Test-PythonModuleCommand([string]$Module) {
    try {
        $null = & $script:PythonExe -m $Module --help 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Ensure-MpRemote() {
    if (Test-PythonModuleCommand 'mpremote') {
        Write-Host 'mpremote is already installed.' -ForegroundColor Green
        return
    }
    Write-Host 'Installing mpremote into your Windows Python environment...'
    if (-not (Test-PythonModuleCommand 'pip')) {
        & $script:PythonExe -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw 'Python pip setup failed.' }
    }
    & $script:PythonExe -m pip install --user --upgrade mpremote
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Retrying mpremote install without --user...'
        & $script:PythonExe -m pip install --upgrade mpremote
        if ($LASTEXITCODE -ne 0) { throw 'Could not install mpremote.' }
    }
    if (-not (Test-PythonModuleCommand 'mpremote')) {
        throw 'mpremote is still unavailable after installation.'
    }
}

function Invoke-MpRemote([string[]]$Arguments) {
    & $script:PythonExe -m mpremote @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "mpremote failed. Close Thonny/other serial consoles and verify the ESP32 COM port."
    }
}

function Test-Board([string]$BoardPort) {
    $output = & $script:PythonExe -m mpremote connect $BoardPort exec 'import sys; print("LABTECH_BOARD=" + sys.implementation.name)' 2>&1
    if ($LASTEXITCODE -ne 0 -or ((@($output) -join [Environment]::NewLine) -notmatch 'LABTECH_BOARD=micropython')) {
        throw 'ESP32 does not appear to be running MicroPython. Flash MicroPython with Thonny and close its serial connection.'
    }
    try {
        $macOutput = & $script:PythonExe -m mpremote connect $BoardPort exec 'import network; w=network.WLAN(network.STA_IF); w.active(True); print("LABTECH_MAC=" + ":".join("%02X" % b for b in w.config("mac")))' 2>&1
        if ($LASTEXITCODE -eq 0) {
            $match = [regex]::Match((@($macOutput) -join ' '), 'LABTECH_MAC=([A-F0-9:]{17})')
            if ($match.Success) {
                Write-Host "ESP32 Wi-Fi MAC: $($match.Groups[1].Value)" -ForegroundColor Cyan
                Write-Host 'Register this MAC under the Cyber City building before provisioning.'
                return
            }
        }
    } catch {
        Write-Host 'MAC auto-detection unavailable; registration must be completed separately.' -ForegroundColor Yellow
    }
}


function Validate-ConfiguredFiles() {
    # Reuse the existing hardened workstation installer validation:
    # syntax, required fields, known placeholders and optional CA presence.
    $validator = Join-Path (Join-Path $FirmwareDirectory 'tools') 'usb_install.py'
    if (-not (Test-Path $validator -PathType Leaf)) {
        throw 'Missing tools/usb_install.py in the extracted ZIP.'
    }
    $output = & $script:PythonExe $validator --port $Port --directory $FirmwareDirectory 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Firmware configuration failed validation. $(@($output) -join ' ')"
    }
}

function Test-BoardModule([string]$Module, [string]$BoardPort) {
    if ($Module -notmatch '^[A-Za-z_]+(\.[A-Za-z_]+)?$') { throw 'Invalid module name' }
    $source = "import $Module; print('LABTECH_MODULE_OK')"
    $check = & $script:PythonExe -m mpremote connect $BoardPort exec $source 2>&1
    return ($LASTEXITCODE -eq 0 -and ((@($check) -join ' ') -match 'LABTECH_MODULE_OK'))
}

function Ensure-BoardModules([string]$BoardPort) {
    if (-not (Test-BoardModule 'umqtt.simple' $BoardPort)) {
        Write-Host 'Installing MicroPython umqtt.simple library...'
        Invoke-MpRemote -Arguments @('connect', $BoardPort, 'mip', 'install', 'umqtt.simple')
        if (-not (Test-BoardModule 'umqtt.simple' $BoardPort)) {
            throw 'umqtt.simple could not be imported after installation.'
        }
    }
    Write-Host 'MicroPython MQTT library OK.' -ForegroundColor Green
    if (-not (Test-BoardModule 'neopixel' $BoardPort)) {
        Write-Host 'Installing MicroPython neopixel (needed for WS2811 strips)...'
        Invoke-MpRemote -Arguments @('connect', $BoardPort, 'mip', 'install', 'neopixel')
        if (-not (Test-BoardModule 'neopixel' $BoardPort)) {
            throw 'neopixel is unavailable. Use an ESP32 MicroPython build with NeoPixel support.'
        }
    }
    Write-Host 'MicroPython NeoPixel / WS2811 library OK.' -ForegroundColor Green
}

function Configure-Device() {
    $bootstrap = Join-Path $FirmwareDirectory 'bootstrap_config.py'
    $mqttConfig = Join-Path $FirmwareDirectory 'mqtt_secrets.py'
    if ((Test-Path $bootstrap) -and (Test-Path $mqttConfig)) {
        if (Confirm-Answer 'Both configured files exist. Reuse them without changing Wi-Fi, MQTT or provisioning secrets?') {
            Write-Host 'Reusing existing configuration.'
            return
        }
    }
    Write-Host ''
    Write-Host 'Enter the Wi-Fi, LabTech and MQTT settings for this ESP32.'
    Write-Host 'LabTech broker host/port and GPIO topics are downloaded from LabTech, not entered here.'
    $ssid = Prompt-Value 'Wi-Fi SSID'
    $wifiPassword = Prompt-Secret 'Wi-Fi password (hidden)'
    $labtechUrl = Prompt-Value 'LabTech HTTPS server URL' 'https://labtech.lccc-itp.org'
    $labtechUrl = $labtechUrl.TrimEnd('/')
    if ($labtechUrl -notmatch '^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?$') {
        throw 'The LabTech URL must be a single https://host[:port] origin.'
    }
    Write-Host 'You must first register the displayed MAC in LabTech Cyber City.'
    Write-Host 'On the LabTech server, use: python manage.py issue_cybercity_esp32_key <MAC>'
    $key = Prompt-Secret 'Device provisioning key from LabTech (hidden)'
    $useMqttCredentials = Confirm-Answer 'Does the Mosquitto broker require a username and password?'
    if ($useMqttCredentials) {
        $mqttUser = Prompt-Value 'MQTT username'
        $mqttPassword = Prompt-Secret 'MQTT password (hidden)'
    } else {
        Write-Host 'Warning: anonymous MQTT is only appropriate on a tightly isolated test broker.' -ForegroundColor Yellow
        $mqttUser = ''
        $mqttPassword = ''
    }
    Write-Host 'LabTech HTTPS certificate checks will be disabled for this classroom lab.' -ForegroundColor Yellow
    Write-Host 'This allows server impersonation; do not use it on shared/public Wi-Fi.' -ForegroundColor Yellow
    Write-Config 'bootstrap_config.py' @(
        '# Cyber City ESP32: generated by the Windows installer.',
        'WIFI_SSID = ' + (To-PythonString $ssid),
        'WIFI_PASSWORD = ' + (To-PythonString $wifiPassword),
        'LABTECH_URL = ' + (To-PythonString $labtechUrl),
        'LABTECH_TLS_VERIFY = False',
        'DEVICE_KEY = ' + (To-PythonString $key)
    )
    Write-Config 'mqtt_secrets.py' @(
        '# Cyber City broker credentials: generated by the Windows installer.',
        'MQTT_USER = ' + (To-PythonString $mqttUser),
        'MQTT_PASSWORD = ' + (To-PythonString $mqttPassword)
    )
}

try {
    Write-Host ''
    Write-Host '==============================================' -ForegroundColor Cyan
    Write-Host '  LabTech Cyber City - ESP32 Windows Installer' -ForegroundColor Cyan
    Write-Host '==============================================' -ForegroundColor Cyan
    Write-Host 'This installs MicroPython application files; it does not reflash the ESP32.'
    Write-Host ''

    if (-not $FirmwareDirectory) { $FirmwareDirectory = $PSScriptRoot }
    $FirmwareDirectory = [System.IO.Path]::GetFullPath($FirmwareDirectory)
    foreach ($name in $ApplicationFiles) {
        if (-not (Test-Path (Join-Path $FirmwareDirectory $name) -PathType Leaf)) {
            throw "Missing $name. Run this from a freshly extracted LabTech Basic ESP32 Firmware ZIP."
        }
    }
    if ($SelfTest) {
        $testString = To-PythonString 'Demo "WiFi" \ key'
        if ($testString -ne '"Demo \"WiFi\" \\ key"') { throw 'String escaping self-test failed.' }
        Write-Host 'PASS: Firmware sources found; Windows configuration generator validated.'
        Write-Host 'No installation was performed and no credentials were requested.'
        exit 0
    }

    Write-Host 'Close Thonny and any other ESP32 serial console before proceeding.' -ForegroundColor Yellow
    $script:PythonExe = Ensure-Python
    Write-Host "Python: $script:PythonExe"
    Ensure-MpRemote
    Write-Host ''
    Write-Host 'Available serial devices:'
    & $script:PythonExe -m mpremote connect list
    if (-not $Port) { $Port = Prompt-Value 'ESP32 COM port (example: COM5)' }
    $Port = $Port.ToUpperInvariant()
    if ($Port -notmatch '^COM[0-9]{1,3}$') { throw "Invalid Windows serial port: $Port" }
    Test-Board $Port

    Configure-Device
    Validate-ConfiguredFiles
    Ensure-BoardModules $Port

    $uploadFiles = [System.Collections.Generic.List[string]]::new()
    foreach ($file in $ApplicationFiles + @('bootstrap_config.py', 'mqtt_secrets.py')) {
        if (-not (Test-Path (Join-Path $FirmwareDirectory $file) -PathType Leaf)) {
            throw "Missing required configured firmware file: $file"
        }
        $uploadFiles.Add($file)
    }
    foreach ($file in $OptionalFiles) {
        if (Test-Path (Join-Path $FirmwareDirectory $file) -PathType Leaf) {
            if ($file -eq 'labtech-ca.der') {
                $bootstrapText = [System.IO.File]::ReadAllText(
                    (Join-Path $FirmwareDirectory 'bootstrap_config.py'))
                if ($bootstrapText -match '(?m)^\s*LABTECH_TLS_VERIFY\s*=\s*True\b') {
                    $uploadFiles.Add($file)
                }
                continue
            }
            if (Confirm-Answer "Also upload optional configuration $file?" $false) {
                $uploadFiles.Add($file)
            }
        }
    }
    Write-Host ''
    Write-Host "Ready to upload $($uploadFiles.Count) files to $Port."
    Write-Host 'boot.py / main.py will not be modified. Credentials are saved in this local extracted folder.'
    if (-not (Confirm-Answer 'Upload now?')) { throw 'Cancelled; no ESP32 application files were uploaded.' }
    $index = 0
    foreach ($file in $uploadFiles) {
        $index++
        Write-Host "[$index/$($uploadFiles.Count)] Uploading $file..."
        $source = Join-Path $FirmwareDirectory $file
        Invoke-MpRemote -Arguments @('connect', $Port, 'fs', 'cp', $source, ':' + $file)
    }
    Write-Host ''
    Write-Host 'SUCCESS: All selected Cyber City firmware files were copied.' -ForegroundColor Green
    Write-Host 'No MicroPython reset, partition erasure or OTA activation was performed.'
    $autostart = $false
    if (Confirm-Answer 'Enable Cyber City automatically after power-on/reboot? (optional)' $false) {
        # Never overwrite an existing student or instructor main.py.
        $listing = & $script:PythonExe -m mpremote connect $Port fs ls 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not inspect the ESP32 filesystem; refusing to change main.py.'
        }
        $hasMain = ((@($listing) -join [Environment]::NewLine) -match '(?m)(^|\s)main\.py($|\s)')
        if ($hasMain) {
            Write-Host 'Existing main.py found. It was NOT replaced. Configure autostart manually if needed.' -ForegroundColor Yellow
        } else {
            $tempMain = Join-Path ([System.IO.Path]::GetTempPath()) ('cybercity-main-' + [guid]::NewGuid().ToString('N') + '.py')
            try {
                $lines = @(
                    '# Cyber City auto-start. Press Ctrl+C at the REPL to interrupt.',
                    'import device_startup',
                    'device_startup.run()'
                )
                $mainContent = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
                [System.IO.File]::WriteAllText(
                    $tempMain, $mainContent, [System.Text.UTF8Encoding]::new($false)
                )
                Invoke-MpRemote -Arguments @('connect', $Port, 'fs', 'cp', $tempMain, ':main.py')
                $autostart = $true
                Write-Host 'Autostart enabled: the device will run on its next reboot.' -ForegroundColor Green
            } finally {
                Remove-Item -LiteralPath $tempMain -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Host 'To start manually in the ESP32 REPL:'
    Write-Host '  import device_startup'
    Write-Host '  device_startup.run()'
    if ($autostart) {
        Write-Host 'Power-cycle or reset the ESP32 to run the new main.py, or test manually now.'
    }
    if (Confirm-Answer 'Open the MicroPython serial console now?') {
        Write-Host 'At >>>, paste the two startup lines above. Press Ctrl+] to exit the console.'
        Invoke-MpRemote -Arguments @('connect', $Port, 'repl')
    }
} catch {
    Write-Host ''
    Write-Host "Installation stopped: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Already copied files are not automatically removed; correct the issue and rerun.'
    exit 1
}
