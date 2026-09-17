@echo off
REM 중복 사진 정리 도구 - exe 빌드 + 설치 프로그램(installer) 빌드 스크립트
REM 사용법: venv 안에서 이 배치파일을 실행하세요.
REM   PhotoDedup> venv\Scripts\activate
REM   PhotoDedup> build.bat

pyinstaller --noconfirm --onefile --windowed --name PhotoDedup ^
    --collect-all tkinterdnd2 ^
    --collect-all imagehash ^
    --collect-all pystray ^
    main.py

echo.
echo exe 빌드 완료: dist\PhotoDedup.exe

REM Inno Setup(ISCC.exe)이 설치되어 있으면 설치 프로그램(Setup.exe)도 함께 빌드합니다.
REM 설치: winget install JRSoftware.InnoSetup  (https://jrsoftware.org/isinfo.php)
set ISCC="%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer.iss
    echo 설치 프로그램 빌드 완료: installer_output\PhotoDedup_Setup_1.1.7.exe
) else (
    echo [안내] Inno Setup(ISCC.exe)을 찾지 못해 설치 프로그램은 건너뛰었습니다.
    echo         "winget install JRSoftware.InnoSetup" 설치 후 다시 실행하면 설치 프로그램까지 만들어집니다.
)

pause
