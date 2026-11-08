@echo off
title Trust KPRIT Smart Attendance SSL Certificate
echo ==============================================================================
echo Installing KPRIT SSL/TLS Certificate into Windows Trusted Root Store
echo This will eliminate the 'Not Secure' browser warning on https://localhost:8501
echo ==============================================================================
echo.

set CERT_PATH=%~dp0..\certs\cert.pem

if not exist "%CERT_PATH%" (
    echo [ERROR] Certificate file not found at: %CERT_PATH%
    echo Please run scripts\generate_ssl_certs.py first.
    pause
    exit /b 1
)

echo Requesting Administrator privileges to install certificate...
powershell -Command "Start-Process certutil -Verb RunAs -ArgumentList '-addstore -f Root \"%CERT_PATH%\"' -Wait"

echo.
echo ==============================================================================
echo Certificate installation complete!
echo Please completely close and restart your browser (Chrome/Edge/Firefox).
echo When you reopen https://localhost:8501, the red warning will be replaced
echo by a trusted secure lock icon.
echo ==============================================================================
pause
