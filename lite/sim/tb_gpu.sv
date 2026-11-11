// ============================================================================
//  File    : sim/tb_gpu.sv
//  Purpose : Full-system test of gpu_core WITHOUT the UART (fast).
//            Reads a scene (scenes/<name>.hex: 4 length bytes, then data),
//            feeds it byte by byte, and
//            writes every reply byte to a hex file for pc/compare.py.
//            Random gaps on input and random backpressure on output check
//            the valid/ready handshakes.
//
//  Plusargs : +SCENE=scenes/cube.hex  +OUT=results/cube_sim.hex
//  Vivado   : see sim/run_xsim.bat      Verilator: see sim/run_verilator.sh
// ============================================================================
`timescale 1ns/1ps
module tb_gpu;
    localparam int MAXB = 65536;

    logic clk = 0, rst_n = 0;
    always #5 clk = ~clk;                         // 100 MHz

    logic       in_valid, in_ready, out_valid, out_ready, busy, overflow;
    logic [7:0] in_data, out_data;
    logic [10:0] tri_count;

    gpu_core #(.W(160), .H(120), .MAX_TRIS(1024)) dut (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_data(in_data), .in_ready(in_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready),
        .busy(busy), .overflow(overflow), .tri_count(tri_count));

    logic [7:0] scene [MAXB];
    string scene_path, out_path;
    int len, fd, sent, received, idle;
    int unsigned seed;

    // simple LCG so xsim and Verilator give the same pattern
    function automatic bit coin(input int pct);
        seed = seed * 1664525 + 1013904223;
        return (seed[31:24] % 100) < pct;
    endfunction

    initial begin
        if (!$value$plusargs("SCENE=%s", scene_path)) scene_path = "scenes/cube.hex";
        if (!$value$plusargs("OUT=%s",   out_path))   out_path   = "results/cube_sim.hex";
        // file layout: 4 length bytes (little-endian), then the scene bytes
        $readmemh(scene_path, scene);
        len = {scene[3], scene[2], scene[1], scene[0]};
        $display("tb: %s, %0d bytes", scene_path, len);
        fd = $fopen(out_path, "w");
        if (fd == 0) begin $display("tb: cannot open %s", out_path); $finish; end

        seed = 32'd12345;  sent = 0;  received = 0;  idle = 0;
        in_valid = 0;  in_data = 0;  out_ready = 0;
        repeat (5) @(posedge clk);
        rst_n = 1;

        // main loop: one iteration per clock
        while (1) begin
            @(posedge clk);
            // transfers that happened on this edge
            if (in_valid && in_ready) sent++;
            if (out_valid && out_ready) begin
                $fwrite(fd, "%02x\n", out_data);
                received++;
            end

            // drive next cycle's inputs (after the edge)
            #1;
            in_valid = (sent < len) && coin(80);
            in_data  = (sent < len) ? scene[sent + 4] : 8'h00;
            out_ready = coin(70);

            if (sent >= len && !busy && !out_valid) idle++; else idle = 0;
            if (idle > 200) break;
        end

        $fclose(fd);
        $display("tb: sent %0d bytes, received %0d bytes -> %s", sent, received, out_path);
        if (overflow) $display("tb: WARNING triangle overflow");
        $finish;
    end

    // safety timeout (10 ms of simulated time)
    initial begin
        #10_000_000;
        $display("tb: TIMEOUT");
        $finish;
    end
endmodule
