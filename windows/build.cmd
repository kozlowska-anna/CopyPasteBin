@echo off
rem CopyPasteBin stage 0 - builds the three test tools with the C# compiler
rem that ships with Windows (.NET Framework 4.x). Nothing is downloaded or
rem installed, no administrator rights are needed, and the output goes only
rem to the "build" folder next to this script.
setlocal

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    echo The built-in C# compiler was not found. Nothing was built.
    exit /b 1
)

set "SRC=%~dp0src"
set "OUT=%~dp0build"
if not exist "%OUT%" mkdir "%OUT%"
if not exist "%OUT%" (
    echo The output folder could not be created. Nothing was built.
    exit /b 1
)

set "COMMON=/nologo /target:exe /platform:anycpu /optimize+ /warn:4 /reference:System.dll /reference:System.Windows.Forms.dll"

"%CSC%" %COMMON% /out:"%OUT%\CpbClipboardProbe.exe" "%SRC%\Native.cs" "%SRC%\Common.cs" "%SRC%\ClipboardProbe.cs"
if errorlevel 1 (
    echo Build FAILED at CpbClipboardProbe. Please copy the compiler messages into the test report.
    exit /b 1
)

"%CSC%" %COMMON% /out:"%OUT%\CpbSyntheticOwner.exe" "%SRC%\Native.cs" "%SRC%\Common.cs" "%SRC%\SyntheticOwner.cs"
if errorlevel 1 (
    echo Build FAILED at CpbSyntheticOwner. Please copy the compiler messages into the test report.
    exit /b 1
)

"%CSC%" %COMMON% /out:"%OUT%\CpbClipboardBlocker.exe" "%SRC%\Native.cs" "%SRC%\Common.cs" "%SRC%\ClipboardBlocker.cs"
if errorlevel 1 (
    echo Build FAILED at CpbClipboardBlocker. Please copy the compiler messages into the test report.
    exit /b 1
)

echo Build finished: %OUT%
exit /b 0
