# Mini GPU Lite: one rasterizer, two FPGAs

A small GPU core in SystemVerilog that draws triangles at **one pixel per clock**,
with a depth (Z) buffer. The **same RTL** runs on:

- **Basys3** (Artix-7): the PC sends triangles over USB-UART
- **ALINX Zynq-7020**: the on-chip ARM sends triangles over AXI-Lite

Every result is checked **bit for bit** against a C++ golden model, and the
cycle count is predicted exactly by a simple formula.

Team of two: **Member 1** builds and measures the hardware; **Member 2** makes the
3D models in Blender (`models/`, rules in `docs/methodology.html`, stage S2b).
Full methodology: `docs/methodology.html`.

## What runs where

| Step | Where |
|---|---|
| 3D transform, projection, lighting (per triangle color) | Host (PC Python or ARM) |
| Triangle setup (edges, area, bounding box, back-face cull) | **FPGA** |
| Rasterization (edge test, 1 pixel per clock) | **FPGA** |
| Depth interpolation and Z-buffer test | **FPGA** |
| Framebuffer, clear, readback | **FPGA** |

Moving the transform onto the FPGA is future work (see the paper notes below).

## Already tested (in this folder, before you got it)

- 5 scenes (cube, sphere, 500 random triangles, fill-rule grid, depth overlap)
- through 3 paths: GPU core alone, full Basys3 design with real UART, Zynq AXI-Lite wrapper
- all 15 runs: **0 pixels different**, all counters equal, **cycle model error = 0**
- the ARM software code in `zynq/main.c` gives the same CRC as the golden model

## Folder map

```
rtl/        uart_rx.sv uart_tx.sv sdp_ram.sv rasterizer.sv depth_unit.sv gpu_core.sv basys3_top.sv
zynq/       gpu_axil.v (AXI-Lite wrapper)  main.c (ARM program)  scene_*.h (made by make_scene.py)
golden/     golden.cpp (bit-exact model + CPU timing)  build.bat
pc/         protocol.py make_scene.py run_board.py compare.py sweep.py check_models.py
            collect_vivado.py make_report.py zynq_log.py
sim/        tb_gpu.sv (core)  tb_top.sv (Basys3 + UART)  tb_axil.sv (Zynq wrapper)
            run_xsim.bat run_xsim_top.bat (Windows/Vivado)  run_verilator.sh run_all.sh (Linux)
vivado/     build_basys3.tcl program_basys3.tcl core_compare.tcl
constraints/ basys3.xdc core_ooc.xdc
models/     Blender exports (*.obj + *.mtl), MODELS.md   (Member 2)
scenes/     *.bin (bytes sent to the GPU)  *.hex (same, for the testbench)
results/    everything the scripts write
```

## Workflow

**Basys3 run**

User runs `python pc/run_board.py cube --port COM5`
→ `pc/make_scene.py` (already run: builds triangles, writes `scenes/cube.bin`)
→ `pc/run_board.py` (sends each command, waits for replies, times upload/readback; passes bytes over UART)
→ `rtl/uart_rx.sv` (serial bits to bytes; passes one byte per pulse)
→ `rtl/gpu_core.sv` (decodes commands, stores triangles, starts DRAW; passes triangle words)
→ `rtl/rasterizer.sv` (setup + walks the box, 1 pixel/clock; passes fragments)
→ `rtl/depth_unit.sv` (depth compare, writes depth + color BRAM; passes the frame on READ)
→ `rtl/uart_tx.sv` (bytes back to the PC)
→ `results/cube_basys3.bin` + `cube_basys3_timing.json`
→ `pc/compare.py` (vs `results/cube_golden.*`; writes PNGs + json) → **PASS/FAIL**

**Zynq run**

`zynq/main.c` (ARM pushes the same bytes) → `zynq/gpu_axil.v` (AXI-Lite registers)
→ same `gpu_core.sv` → back through `gpu_axil.v` → `main.c` prints cycles, CRC, times,
**and** runs the same algorithm in software on the ARM → `pc/zynq_log.py` → `pc/compare.py`

**Complete map**

```
make_scene.py → scenes/X.bin ─┬→ golden.cpp → results/X_golden.bin/.json (truth, CPU time, cycle model)
                              ├→ tb_gpu / tb_top / tb_axil (simulation) → results/X_sim.hex ┐
                              ├→ run_board.py → uart_rx → gpu_core → rasterizer → depth_unit → uart_tx → X_basys3.bin ┤
                              └→ scene_X.h → main.c → gpu_axil → gpu_core ... → terminal log → zynq_log.py → X_zynq.bin ┤
                                                                                     compare.py ←─────────────────────┘
compare.py → results/X_<platform>.json → make_report.py → results_table.csv/.md
core_compare.tcl → *_core_*.rpt → collect_vivado.py → fpga_compare.csv
sweep.py → many random scenes → sweep.csv
```

## Setup on Windows (one time)

1. **Python 3**: `pip install pyserial`
2. **A C++ compiler** for the golden model: MSYS2 `g++`, or Visual Studio Build Tools.
   Then, from the `lite` folder: `golden\build.bat`
3. **Vivado 2024 + Vitis**: you have them. Open a terminal where Vivado is on PATH
   (run `settings64.bat` from your Vivado install folder first).

## Commands, in order

```bat
REM 1. scenes + golden
python pc\make_scene.py cube
python pc\make_scene.py obj models\torus.obj --angle 20 --tilt 35
python pc\check_models.py            (Member 2: previews of every model)
golden\golden.exe scenes\cube.bin results\cube

REM 2. simulate in Vivado (must say RESULT: PASS)
sim\run_xsim.bat cube
sim\run_xsim_top.bat cube

REM 3. Basys3
vivado -mode batch -source vivado\build_basys3.tcl
vivado -mode batch -source vivado\program_basys3.tcl
python pc\run_board.py cube --port COM5 --draws 10
python pc\compare.py cube results\cube_basys3.bin --tag basys3 --timing results\cube_basys3_timing.json

REM 4. both chips, same core: resources, Fmax, power
vivado -mode batch -source vivado\core_compare.tcl
python pc\collect_vivado.py

REM 5. size sweep on the board, then the final table
python pc\sweep.py --port COM5
python pc\make_report.py
```

Find the COM port in Device Manager → Ports (the Basys3 shows two USB serial
ports; the UART one is usually the higher number). If 921600 baud gives errors,
use `--baud 115200` **and** rebuild with `CLKS_PER_BIT = 868` in `basys3_top.sv`.

## Zynq steps (Vivado block design)

1. New RTL project, part from your ALINX manual (`xc7z020clg400-2` for most AX7020 boards).
2. Add sources: `zynq/gpu_axil.v`, `rtl/sdp_ram.sv`, `rtl/rasterizer.sv`, `rtl/depth_unit.sv`, `rtl/gpu_core.sv`.
3. Create Block Design → add **ZYNQ7 Processing System** → Run Block Automation.
   Use ALINX's board preset for DDR/MIO settings (from the ALINX download package).
4. Right-click the canvas → **Add Module** → `gpu_axil`.
5. Run Connection Automation (connects it to `M_AXI_GP0`, clock and reset).
   Set **FCLK_CLK0 = 100 MHz** in the PS settings.
6. Address Editor: note the base address of `gpu_axil_0`.
7. Create HDL Wrapper → Generate Bitstream → File → Export → Export Hardware (include bitstream).
8. Vitis: new platform from the `.xsa` → new "Hello World" app → replace its source
   with `zynq/main.c` + `zynq/scene_cube.h`. If `GPU_BASE` is wrong, set it from step 6.
9. Run, open the serial terminal at 115200. `crc32` must equal `results/cube_golden.json`.
   For the full image check, set `DUMP_FRAME 1`, save the log, run
   `python pc\zynq_log.py log.txt cube` then `compare.py ... --tag zynq`.

If the Zynq board fights you, `core_compare.tcl` still gives you the Zynq resource,
timing and power numbers. Say "implementation only" in the paper for that part.

## Honest numbers (from simulation, 100 MHz)

| Scene | Pixels tested | FPGA time | Desktop CPU (1 core) |
|---|---|---|---|
| cube | 14,890 | 0.15 ms | ~0.02 ms |
| random 500 tris | 56,515 | 0.60 ms | ~0.25 ms |
| random, 64 px tris | 456,466 | 4.6 ms | ~1.1 ms |

A modern desktop core (3+ GHz) beats a 1-pixel-per-clock design at 100 MHz.
**Do not claim the FPGA is faster than a PC.** The fair, interesting comparisons are:

1. **FPGA fabric vs the ARM Cortex-A9 on the same Zynq chip** (main.c measures both)
2. **Energy per frame**: Vivado power (~0.1 W range) vs CPU power
3. **Basys3 vs Zynq**: same RTL, different resources, Fmax, host link
4. **I/O bottleneck**: upload + readback over UART vs compute time
5. **Cycle model**: `cycles = 3 + sum(5 if culled else 6 + box_width*box_height)`, error 0

## Paper notes

Working title: *One Rasterizer, Two FPGAs: a bit-exact, open-source comparison of a
fixed-function triangle rasterizer on Artix-7 and Zynq-7000 against embedded and desktop CPUs.*

Realistic target: student conference, workshop, or arXiv. Sections: introduction,
background (edge functions, Pineda 1988; top-left fill rule), design (pipeline, cycle
model, depth hazard and why setup latency hides it), verification (golden model,
3 testbenches), results (tables above + `sweep.csv`, `fpga_compare.csv`), discussion
(where each platform wins), future work (2/4 pixels per clock, transform on FPGA, DMA).
