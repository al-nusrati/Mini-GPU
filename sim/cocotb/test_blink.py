"""
==============================================================================
 File    : sim/cocotb/test_blink.py
 Purpose : First cocotb test. Same pattern every later module test will use:
             1. start a clock   2. reset   3. drive / watch   4. assert
 Run     : cd sim/cocotb && make            (Verilator, from WSL2/Linux)
==============================================================================
"""
import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

TOGGLE = 8   # must match -GTOGGLE_CYCLES in the Makefile


async def reset(dut):
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1


@cocotb.test()
async def led_starts_low_after_reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    await reset(dut)
    await RisingEdge(dut.clk)
    assert int(dut.led.value) == 0, "LED must be 0 right after reset"


@cocotb.test()
async def led_toggles_every_n_cycles(dut):
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    await reset(dut)

    # record the cycle number of every LED change for 5 toggles
    changes, last, cycle = [], int(dut.led.value), 0
    while len(changes) < 5:
        await RisingEdge(dut.clk)
        cycle += 1
        now = int(dut.led.value)
        if now != last:
            changes.append(cycle)
            last = now
        assert cycle < 1000, "LED never toggled"

    gaps = [b - a for a, b in zip(changes, changes[1:])]
    logging.getLogger("test_blink").info(f"toggle cycles: {changes}, gaps: {gaps}")
    assert all(g == TOGGLE for g in gaps), f"expected a toggle every {TOGGLE} cycles, got {gaps}"
