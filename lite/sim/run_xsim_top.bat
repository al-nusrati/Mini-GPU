@echo off
REM  sim\run_xsim_top.bat <scene>   full Basys3 design incl. UART (slower)
set SCENE=%1
if "%SCENE%"=="" set SCENE=cube
if not exist results mkdir results
golden\golden.exe scenes\%SCENE%.bin results\%SCENE% || goto :err
call xvlog -sv rtl\uart_rx.sv rtl\uart_tx.sv rtl\sdp_ram.sv rtl\rasterizer.sv rtl\depth_unit.sv rtl\gpu_core.sv rtl\basys3_top.sv sim\tb_top.sv || goto :err
call xelab tb_top -s tb_top_sim -timescale 1ns/1ps || goto :err
call xsim tb_top_sim -R -testplusarg SCENE=scenes/%SCENE%.hex -testplusarg OUT=results/%SCENE%_top.hex || goto :err
python pc\compare.py %SCENE% results\%SCENE%_top.hex --tag top --skip 4
goto :eof
:err
echo FAILED
