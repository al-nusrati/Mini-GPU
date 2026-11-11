@echo off
REM ===========================================================================
REM  sim\run_xsim.bat <scene>     (Windows, Vivado 2024 installed)
REM  Run from the lite\ folder in a terminal where Vivado is on PATH, e.g.
REM     call C:\Xilinx\Vivado\2024.2\settings64.bat
REM     sim\run_xsim.bat cube
REM ===========================================================================
set SCENE=%1
if "%SCENE%"=="" set SCENE=cube
if not exist results mkdir results

golden\golden.exe scenes\%SCENE%.bin results\%SCENE% || goto :err

call xvlog -sv rtl\sdp_ram.sv rtl\rasterizer.sv rtl\depth_unit.sv rtl\gpu_core.sv sim\tb_gpu.sv || goto :err
call xelab tb_gpu -s tb_gpu_sim -timescale 1ns/1ps || goto :err
call xsim tb_gpu_sim -R -testplusarg SCENE=scenes/%SCENE%.hex -testplusarg OUT=results/%SCENE%_sim.hex || goto :err

python pc\compare.py %SCENE% results\%SCENE%_sim.hex --tag sim
goto :eof
:err
echo FAILED
