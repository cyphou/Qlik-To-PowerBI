param(
    [Parameter(Mandatory = $true)]
    [string]$PbipPath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedTitle,
    [int]$TimeoutSeconds = 90,
    [string]$DesktopExe = "",
    [switch]$KeepOpen
)

$ErrorActionPreference = "Stop"

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class DesktopOpenabilityWindows {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr extra);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc callback, IntPtr extra);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int max);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
}
'@

function Find-PowerBIDesktop {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (-not (Test-Path $ExplicitPath -PathType Leaf)) {
            throw "Power BI Desktop executable not found: $ExplicitPath"
        }
        return (Resolve-Path $ExplicitPath).Path
    }

    $app = Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending |
        Select-Object -First 1
    if ($app) {
        $candidate = Join-Path $app.InstallLocation "bin\PBIDesktop.exe"
        if (Test-Path $candidate -PathType Leaf) {
            return $candidate
        }
    }

    $classic = Join-Path $env:ProgramFiles "Microsoft Power BI Desktop\bin\PBIDesktop.exe"
    if (Test-Path $classic -PathType Leaf) {
        return $classic
    }

    throw "Power BI Desktop executable was not found. Use --desktop-exe."
}

function Get-WorkspacePortFiles {
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\Power BI Desktop\AnalysisServicesWorkspaces"),
        (Join-Path $env:USERPROFILE "Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces")
    )
    $files = @()
    foreach ($root in $roots) {
        if (Test-Path $root -PathType Container) {
            $files += Get-ChildItem $root -Filter "msmdsrv.port.txt" -File -Recurse -ErrorAction SilentlyContinue
        }
    }
    return @($files)
}

function Get-DesktopMsmdsrvProcess {
    param(
        [int]$DesktopProcessId,
        [datetime]$StartedAt
    )

    $all = @(Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" -ErrorAction SilentlyContinue)
    if (-not $all) {
        return $null
    }

    $directChild = $all |
        Where-Object { $_.ParentProcessId -eq $DesktopProcessId } |
        Select-Object -First 1
    if ($directChild) {
        return $directChild
    }

    $recentWithWorkspace = $all |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match 'AnalysisServicesWorkspace_' -and
            $_.CreationDate -and
            $_.CreationDate -ge $StartedAt.AddMinutes(-1)
        } |
        Sort-Object CreationDate -Descending |
        Select-Object -First 1

    return $recentWithWorkspace
}

function Get-PortFromMsmdsrvProcess {
    param($ProcessObject)

    if (-not $ProcessObject) {
        return $null
    }

    $commandLine = [string]$ProcessObject.CommandLine
    if (-not $commandLine) {
        return $null
    }

    $match = [regex]::Match($commandLine, '-s\s+"([^"]+)"')
    if (-not $match.Success) {
        return $null
    }

    $dataDir = $match.Groups[1].Value
    if (-not $dataDir) {
        return $null
    }

    $portFile = Join-Path $dataDir "msmdsrv.port.txt"
    if (-not (Test-Path $portFile -PathType Leaf)) {
        return $null
    }

    $portText = (Get-Content $portFile -Raw).Trim([char]0).Trim()
    $parsedPort = 0
    if ([int]::TryParse($portText, [ref]$parsedPort)) {
        return [ordered]@{
            port = $parsedPort
            workspace_data_dir = $dataDir
            port_file = $portFile
            source = "msmdsrv_process"
        }
    }
    return $null
}

function Get-PortFromProcessSockets {
    param([int]$ProcessId)

    if (-not $ProcessId) {
        return $null
    }

    $port = $null
    try {
        $listen = Get-NetTCPConnection -OwningProcess $ProcessId -State Listen -ErrorAction SilentlyContinue |
            Where-Object {
                $_.LocalPort -gt 0 -and (
                    $_.LocalAddress -eq '127.0.0.1' -or
                    $_.LocalAddress -eq '::1' -or
                    $_.LocalAddress -eq '0.0.0.0' -or
                    $_.LocalAddress -eq '::'
                )
            } |
            Sort-Object LocalPort |
            Select-Object -First 1
        if ($listen) {
            $port = [int]$listen.LocalPort
        }
    }
    catch {
    }

    if (-not $port) {
        $lines = netstat -ano -p tcp | Select-String "LISTENING\s+$ProcessId$"
        foreach ($line in $lines) {
            $parts = ($line.ToString() -replace '^\s+', '') -split '\s+'
            if ($parts.Count -ge 2) {
                $endpoint = $parts[1]
                $idx = $endpoint.LastIndexOf(':')
                if ($idx -gt 0) {
                    $candidate = 0
                    if ([int]::TryParse($endpoint.Substring($idx + 1), [ref]$candidate) -and $candidate -gt 0) {
                        $port = $candidate
                        break
                    }
                }
            }
        }
    }

    if (-not $port) {
        return $null
    }

    return [ordered]@{
        port = [int]$port
        workspace_data_dir = ""
        port_file = ""
        source = "msmdsrv_socket"
    }
}

function Get-PortFromWorkspaceFallback {
    param([datetime]$StartedAt)

    $candidate = Get-WorkspacePortFiles |
        Where-Object { $_.LastWriteTime -ge $StartedAt.AddMinutes(-2) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $candidate) {
        $candidate = Get-WorkspacePortFiles |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if (-not $candidate) {
            return $null
        }
    }

    $portText = (Get-Content $candidate.FullName -Raw).Trim([char]0).Trim()
    $parsedPort = 0
    if (-not [int]::TryParse($portText, [ref]$parsedPort)) {
        return $null
    }

    return [ordered]@{
        port = $parsedPort
        workspace_data_dir = Split-Path $candidate.FullName -Parent
        port_file = $candidate.FullName
        source = "workspace_fallback"
    }
}

function Get-VisibleWindows {
    param([int]$ProcessId)

    $script:desktopProbeWindows = @()
    [DesktopOpenabilityWindows]::EnumWindows({
        param($handle, $extra)
        [uint32]$windowProcessId = 0
        [void][DesktopOpenabilityWindows]::GetWindowThreadProcessId($handle, [ref]$windowProcessId)
        if ($windowProcessId -eq $ProcessId -and [DesktopOpenabilityWindows]::IsWindowVisible($handle)) {
            $title = [Text.StringBuilder]::new(1024)
            [void][DesktopOpenabilityWindows]::GetWindowText($handle, $title, $title.Capacity)
            if ($title.Length -gt 0) {
                $script:desktopProbeWindows += $title.ToString()
            }
        }
        return $true
    }, [IntPtr]::Zero) | Out-Null
    return @($script:desktopProbeWindows | Sort-Object -Unique)
}

function Find-AdomdAssembly {
    param([string]$DesktopPath)

    $bin = Split-Path $DesktopPath -Parent
    $candidate = Join-Path $bin "Microsoft.PowerBI.AdomdClient.dll"
    if (Test-Path $candidate -PathType Leaf) {
        $stagingRoot = Join-Path $env:TEMP "qtpbi_adomd"
        $stagingDir = Join-Path $stagingRoot ((Get-Date).ToString("yyyyMMdd"))
        New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

        $patterns = @(
            "Microsoft.PowerBI.AdomdClient.dll",
            "Microsoft.AnalysisServices*.dll"
        )
        foreach ($pattern in $patterns) {
            Get-ChildItem $bin -Filter $pattern -File -ErrorAction SilentlyContinue |
                ForEach-Object {
                    Copy-Item -Path $_.FullName -Destination (Join-Path $stagingDir $_.Name) -Force -ErrorAction SilentlyContinue
                }
        }

        $staged = Join-Path $stagingDir "Microsoft.PowerBI.AdomdClient.dll"
        if (Test-Path $staged -PathType Leaf) {
            return $staged
        }

        return $candidate
    }
    throw "Microsoft.PowerBI.AdomdClient.dll not found beside Power BI Desktop."
}

function Get-DmvRowCount {
    param(
        [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]$Connection,
        [string]$Query
    )

    $command = $Connection.CreateCommand()
    $command.CommandText = $Query
    $reader = $command.ExecuteReader()
    $count = 0
    try {
        while ($reader.Read()) {
            $count += 1
        }
    }
    finally {
        $reader.Dispose()
        $command.Dispose()
    }
    return $count
}

function Get-LiveModelMetadata {
    param(
        [int]$Port,
        [string]$AdomdAssembly
    )

    [void][Reflection.Assembly]::LoadFrom($AdomdAssembly)
    $connection = [Microsoft.AnalysisServices.AdomdClient.AdomdConnection]::new(
        "Data Source=localhost:$Port;Application Name=QlikToPowerBI-DesktopOpenability"
    )
    $connection.Open()
    try {
        return [ordered]@{
            table_count = Get-DmvRowCount $connection 'SELECT [Name] FROM $SYSTEM.TMSCHEMA_TABLES'
            relationship_count = Get-DmvRowCount $connection 'SELECT [Name] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS'
        }
    }
    finally {
        $connection.Close()
        $connection.Dispose()
    }
}

function Get-FrownFiles {
    $root = Join-Path $env:USERPROFILE "Microsoft\Power BI Desktop Store App"
    if (-not (Test-Path $root -PathType Container)) {
        return @()
    }
    return @(Get-ChildItem $root -Filter "FrownSnapShot*.zip" -File -ErrorAction SilentlyContinue)
}

$resolvedPbip = (Resolve-Path $PbipPath).Path
$desktopPath = Find-PowerBIDesktop $DesktopExe
$adomdAssembly = Find-AdomdAssembly $desktopPath
$baselineFrowns = @{}
foreach ($file in Get-FrownFiles) {
    $baselineFrowns[$file.FullName] = $true
}

$startedAt = Get-Date
$desktopProcess = Start-Process -FilePath $desktopPath -ArgumentList @("`"$resolvedPbip`"") -PassThru
$observation = [ordered]@{
    status = "timeout"
    process_id = $desktopProcess.Id
    process_responding = $false
    title = ""
    visible_windows = @()
    port = $null
    workspace_data_dir = ""
    port_file = ""
    port_source = ""
    msmdsrv_pid = $null
    table_count = $null
    relationship_count = $null
    metadata_error = ""
    new_frowns = @()
    duration_seconds = 0.0
}

try {
    $deadline = $startedAt.AddSeconds([Math]::Max(5, $TimeoutSeconds))
    while ((Get-Date) -lt $deadline) {
        $process = Get-Process -Id $desktopProcess.Id -ErrorAction SilentlyContinue
        if (-not $process) {
            $observation.status = "desktop_exited"
            break
        }

        $observation.process_responding = [bool]$process.Responding
        $windows = @(Get-VisibleWindows $desktopProcess.Id)
        $observation.visible_windows = $windows
        $matchingTitle = $windows | Where-Object { $_ -eq $ExpectedTitle } | Select-Object -First 1
        if ($matchingTitle) {
            $observation.title = $matchingTitle
        }
        elseif ($windows.Count -gt 0) {
            $observation.title = [string]$windows[0]
        }

        if (-not $observation.port) {
            $childMsmdsrv = Get-DesktopMsmdsrvProcess $desktopProcess.Id $startedAt
            if ($childMsmdsrv) {
                $observation.msmdsrv_pid = [int]$childMsmdsrv.ProcessId
            }
            $portFromChild = Get-PortFromMsmdsrvProcess $childMsmdsrv
            if ($portFromChild) {
                $observation.port = [int]$portFromChild.port
                $observation.workspace_data_dir = [string]$portFromChild.workspace_data_dir
                $observation.port_file = [string]$portFromChild.port_file
                $observation.port_source = [string]$portFromChild.source
            }
            else {
                if ($childMsmdsrv) {
                    $portFromSocket = Get-PortFromProcessSockets $childMsmdsrv.ProcessId
                    if ($portFromSocket) {
                        $observation.port = [int]$portFromSocket.port
                        $observation.workspace_data_dir = [string]$portFromSocket.workspace_data_dir
                        $observation.port_file = [string]$portFromSocket.port_file
                        $observation.port_source = [string]$portFromSocket.source
                    }
                }

                if (-not $observation.port) {
                $fallback = Get-PortFromWorkspaceFallback $startedAt
                if ($fallback) {
                    $observation.port = [int]$fallback.port
                    $observation.workspace_data_dir = [string]$fallback.workspace_data_dir
                    $observation.port_file = [string]$fallback.port_file
                    $observation.port_source = [string]$fallback.source
                }
                }
            }
        }

        if ($observation.port -and $matchingTitle -and $process.Responding) {
            try {
                $metadata = Get-LiveModelMetadata $observation.port $adomdAssembly
                $observation.table_count = $metadata.table_count
                $observation.relationship_count = $metadata.relationship_count
                $observation.status = "model_loaded"
                break
            }
            catch {
                $observation.metadata_error = $_.Exception.Message
            }
        }

        [Threading.Thread]::Sleep(500)
    }
}
finally {
    $observation.duration_seconds = [Math]::Round(((Get-Date) - $startedAt).TotalSeconds, 3)
    $observation.new_frowns = @(
        Get-FrownFiles |
            Where-Object { -not $baselineFrowns.ContainsKey($_.FullName) } |
            Select-Object -ExpandProperty FullName
    )
    if (-not $KeepOpen) {
        Stop-Process -Id $desktopProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

$observation | ConvertTo-Json -Depth 6 -Compress