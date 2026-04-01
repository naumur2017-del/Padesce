$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"
$managePath = Join-Path $projectRoot "manage.py"
$taskName = "NAUMUR_Daily_App_Report"
$triggerTime = "17:30"

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$managePath`" send_daily_app_report"
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
Write-Host "Tache planifiee '$taskName' installee a $triggerTime."
