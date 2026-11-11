#!/bin/bash
# =============================================================================
#  sim/run_verilator.sh <scene>   (Linux / WSL; Vivado users: run_xsim.bat)
#  Builds the testbench once, runs one scene, then compares with golden.
# =============================================================================
set -e
cd "$(dirname "$0")/.."
SCENE=${1:-cube}
if [ ! -x sim/obj_dir/Vtb_gpu ]; then
  verilator --binary --timing -Wno-fatal -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND -Mdir sim/obj_dir \
    --top-module tb_gpu sim/tb_gpu.sv rtl/sdp_ram.sv rtl/rasterizer.sv rtl/depth_unit.sv rtl/gpu_core.sv >/dev/null
fi
mkdir -p results
./golden/golden scenes/$SCENE.bin results/$SCENE
sim/obj_dir/Vtb_gpu +SCENE=scenes/$SCENE.hex +OUT=results/${SCENE}_sim.hex
python3 pc/compare.py $SCENE results/${SCENE}_sim.hex --tag sim
