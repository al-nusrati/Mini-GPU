@echo off
REM Build the golden model on Windows. Needs g++ (MinGW / MSYS2) OR run from
REM "x64 Native Tools Command Prompt for VS" for cl.
where g++ >nul 2>nul && (g++ -O2 -std=c++17 golden\golden.cpp -o golden\golden.exe & goto :done)
where cl  >nul 2>nul && (cl /O2 /std:c++17 /EHsc golden\golden.cpp /Fe:golden\golden.exe /Fo:golden\ & goto :done)
echo No C++ compiler found. Install MSYS2 g++ or Visual Studio Build Tools.
:done
