@echo off
echo ============================================
echo   VRC-FISH! - Building standalone .exe
echo ============================================

pyinstaller --onefile --windowed --name VRC-FISH ^
  --add-data "src\models;models" ^
  --collect-all onnxruntime ^
  src\main.py

echo.
echo ============================================
echo   Done! Your .exe is at: dist\VRC-FISH.exe
echo   Test it on a clean machine with no Python
echo   installed to make sure everything is bundled.
echo ============================================
pause