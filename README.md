# Mini GPU

A fixed-function GPU in SystemVerilog, running on Basys3 (Artix-7) and ALINX Zynq-7020,
drawing 3D models with all math on the FPGA. Linked to OpenGL and CUDA through the `mgl` API.

## Repo layout (Week 1)

```
spec/formats.yaml        single source of truth: number formats, structs, packets
tools/gen_types.py       generates the three files below from the spec
tools/test_spec.py       checks the generated files agree (Python + C++)
sw/generated/types.h     GENERATED  C++ types, converters, opcodes
sw/generated/packets.py  GENERATED  Python packet encoder/decoder
rtl/pkg/gpu_pkg.sv       GENERATED  SystemVerilog package
sw/tests/check_types.cpp C++ side of the rounding check
rtl/top/blink.sv         Week 1 hello-hardware module
rtl/top/basys3_top.sv    Basys3 top (blink + SPEC_VERSION on LEDs)
rtl/top/zynq_top.sv      Zynq PL top (fill pins first)
constraints/*.xdc        pin files
sim/cocotb/              first cocotb test (blink)
vivado/*.tcl             scripted builds, no GUI clicking
docs/week1_notes.md      OpenGL -> hardware mapping notes
```

## Rule: never edit generated files

Change `spec/formats.yaml`, then:

```
python tools/gen_types.py
python tools/test_spec.py
```

## Week 1 checks

```
# 1. spec + generators (Windows or Linux, needs: pip install pyyaml)
python tools/gen_types.py
python tools/test_spec.py

# 2. C++ and Python round exactly the same way
g++ -std=c++17 -Isw/generated sw/tests/check_types.cpp -o check_types
python tools/test_spec.py --cpp ./check_types

# 3. simulation (WSL2/Linux, Verilator >= 5.036 for cocotb 2.x)
cd sim/cocotb && make

# 4. Basys3 bitstream and programming
vivado -mode batch -source vivado/build_basys3.tcl
vivado -mode batch -source vivado/program_basys3.tcl
```

Basys3 result: LED0 toggles every 0.5 s, LED1 four times faster, LED15..12 show
`SPEC_VERSION` (0001), holding the center button resets.
