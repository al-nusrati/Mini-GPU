// ============================================================================
//  File    : sim/tb_axil.sv
//  Purpose : Tests zynq/gpu_axil.v exactly the way zynq/main.c uses it:
//            poll STATUS, write TX, read RX. Runs a whole scene through AXI.
//  Plusargs : +SCENE=scenes/cube.hex  +OUT=results/cube_axil.hex
// ============================================================================
`timescale 1ns/1ps
module tb_axil;
    localparam int MAXB = 65536;
    logic clk = 0, rstn = 0;
    always #5 clk = ~clk;

    logic [4:0]  awaddr, araddr;
    logic        awvalid, awready, wvalid, wready, bvalid, bready, arvalid, arready, rvalid, rready;
    logic [31:0] wdata, rdata;
    logic [3:0]  wstrb;
    logic [1:0]  bresp, rresp;

    gpu_axil dut (
        .s_axi_aclk(clk), .s_axi_aresetn(rstn),
        .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(wstrb), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready));

    // Signals are driven and checked on the FALLING edge, so there is no race
    // with the DUT, which changes them on the rising edge.
    task automatic axi_write(input logic [4:0] a, input logic [31:0] d);
        @(negedge clk);
        awaddr = a; awvalid = 1; wdata = d; wstrb = 4'hF; wvalid = 1; bready = 0;
        do @(negedge clk); while (!(awready && wready));   // handshake on next rising edge
        @(negedge clk);
        awvalid = 0; wvalid = 0;
        while (!bvalid) @(negedge clk);
        bready = 1;                                          // accept response on next rising edge
        @(negedge clk);
        bready = 0;
    endtask

    task automatic axi_read(input logic [4:0] a, output logic [31:0] d);
        @(negedge clk);
        araddr = a; arvalid = 1; rready = 0;
        do @(negedge clk); while (!arready);
        @(negedge clk);
        arvalid = 0;
        while (!rvalid) @(negedge clk);
        d = rdata;
        rready = 1;                                          // accept on next rising edge
        @(negedge clk);
        rready = 0;
    endtask

    // the same two helpers zynq/main.c has
    task automatic gpu_put(input logic [7:0] b);
        logic [31:0] st;
        do axi_read(5'h04, st); while (!st[0]);
        axi_write(5'h00, {24'd0, b});
    endtask
    task automatic gpu_get(output logic [7:0] b);
        logic [31:0] r;
        do axi_read(5'h08, r); while (!r[8]);
        b = r[7:0];
    endtask

    logic [7:0] scene [MAXB];
    string scene_path, out_path;
    int len, fd, i, op, need, nrep;
    logic [31:0] id;
    logic [7:0]  b;

    initial begin
        if (!$value$plusargs("SCENE=%s", scene_path)) scene_path = "scenes/cube.hex";
        if (!$value$plusargs("OUT=%s",   out_path))   out_path   = "results/cube_axil.hex";
        $readmemh(scene_path, scene);
        len = {scene[3], scene[2], scene[1], scene[0]};
        fd  = $fopen(out_path, "w");
        awvalid = 0; wvalid = 0; bready = 0; arvalid = 0; rready = 0;
        awaddr = 0; araddr = 0; wdata = 0; wstrb = 0;
        repeat (5) @(posedge clk);
        rstn = 1;

        $display("tb_axil: reading ID");
        axi_read(5'h0C, id);
        $display("tb_axil: ID = %h (expect 47505501)", id);

        i = 0;
        while (i < len) begin
            op   = scene[4 + i];
            need = (op == 1) ? 3 : (op == 2) ? 27 : 1;
            for (int k = 0; k < need; k++) gpu_put(scene[4 + i + k]);
            nrep = (op == 0) ? 4 : (op == 1 || op == 5) ? 1 : (op == 3) ? 17 : (op == 4) ? 160 * 120 * 2 : 0;
            for (int k = 0; k < nrep; k++) begin
                gpu_get(b);
                $fwrite(fd, "%02x\n", b);
            end
            i += need;
        end
        $fclose(fd);
        $display("tb_axil: done, %0d scene bytes", len);
        $finish;
    end
endmodule
