#!/bin/bash
# sim/run_all.sh : every scene through all three testbenches (Linux / WSL)
set -e
cd "$(dirname "$0")/.."
g++ -O2 -std=c++17 golden/golden.cpp -o golden/golden
VFLAGS="--binary --timing -Wno-fatal -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND"
CORE="rtl/sdp_ram.sv rtl/rasterizer.sv rtl/depth_unit.sv rtl/gpu_core.sv"
verilator $VFLAGS -Mdir sim/obj_dir  --top-module tb_gpu  sim/tb_gpu.sv  $CORE >/dev/null
verilator $VFLAGS -Mdir sim/obj_top  --top-module tb_top  sim/tb_top.sv  rtl/*.sv >/dev/null
verilator $VFLAGS -Mdir sim/obj_axil --top-module tb_axil sim/tb_axil.sv zynq/gpu_axil.v $CORE >/dev/null
for s in cube sphere random grid overlap; do
  python3 pc/make_scene.py $s >/dev/null
  ./golden/golden scenes/$s.bin results/$s >/dev/null
  sim/obj_dir/Vtb_gpu   +SCENE=scenes/$s.hex +OUT=results/${s}_sim.hex  >/dev/null
  sim/obj_top/Vtb_top   +SCENE=scenes/$s.hex +OUT=results/${s}_top.hex  >/dev/null
  sim/obj_axil/Vtb_axil +SCENE=scenes/$s.hex +OUT=results/${s}_axil.hex >/dev/null
  python3 pc/compare.py $s results/${s}_sim.hex  --tag sim          | tail -1 | sed "s/^/$s core : /"
  python3 pc/compare.py $s results/${s}_top.hex  --tag top --skip 4 | tail -1 | sed "s/^/$s uart : /"
  python3 pc/compare.py $s results/${s}_axil.hex --tag axil         | tail -1 | sed "s/^/$s axi  : /"
done
python3 pc/make_report.py
