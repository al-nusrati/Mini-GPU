// ============================================================================
//  File    : sim/tb_top.sv
//  Purpose : Tests the REAL Basys3 design (basys3_top: UART + GPU) the way the
//            PC will talk to it: bytes go in on RsRx as serial bits, replies
//            come out on RsTx. Uses a fast baud (8 clocks/bit) so it runs quick.
//  Plusargs : +SCENE=scenes/cube.hex  +OUT=results/cube_top.hex
//  Note    : like the real PC script, it waits for each command's reply
//            before sending the next command that expects one.
// ============================================================================
`timescale 1ns/1ps
module tb_top;
    localparam int CPB  = 8;               // clocks per bit in this test
    localparam int MAXB = 65536;

    logic clk = 0;
    always #5 clk = ~clk;

    logic btnC = 1, rx_line = 1, tx_line;
    logic [15:0] led;

    basys3_top #(.CLKS_PER_BIT(CPB)) dut (
        .clk(clk), .btnC(btnC), .RsRx(rx_line), .RsTx(tx_line), .led(led));

    logic [7:0] scene [MAXB];
    string scene_path, out_path;
    int len, fd, received;

    // ---------------- host -> FPGA: send one byte as serial bits ------------
    task automatic send_byte(input logic [7:0] b);
        rx_line = 0;                       repeat (CPB) @(posedge clk);   // start
        for (int i = 0; i < 8; i++) begin
            rx_line = b[i];                repeat (CPB) @(posedge clk);
        end
        rx_line = 1;                       repeat (CPB) @(posedge clk);   // stop
    endtask

    // ---------------- FPGA -> host: receive bytes forever -------------------
    initial begin
        received = 0;
        forever begin
            logic [7:0] b;
            @(negedge tx_line);                                    // start bit
            repeat (CPB / 2) @(posedge clk);
            for (int i = 0; i < 8; i++) begin
                repeat (CPB) @(posedge clk);
                b[i] = tx_line;
            end
            repeat (CPB) @(posedge clk);                           // stop bit
            $fwrite(fd, "%02x\n", b);
            received++;
        end
    end

    task automatic wait_replies(input int n);
        int target;
        target = received + n;
        while (received < target) @(posedge clk);
    endtask

    initial begin
        int i, op, need;
        if (!$value$plusargs("SCENE=%s", scene_path)) scene_path = "scenes/cube.hex";
        if (!$value$plusargs("OUT=%s",   out_path))   out_path   = "results/cube_top.hex";
        $readmemh(scene_path, scene);
        len = {scene[3], scene[2], scene[1], scene[0]};
        fd  = $fopen(out_path, "w");
        repeat (10) @(posedge clk);
        btnC = 0;
        repeat (10) @(posedge clk);

        // PING first (like run_board.py)
        send_byte(8'h00);
        wait_replies(4);

        i = 0;
        while (i < len) begin
            op = scene[4 + i];
            need = (op == 1) ? 3 : (op == 2) ? 27 : 1;               // command size
            for (int k = 0; k < need; k++) send_byte(scene[4 + i + k]);
            case (op)
                1, 5: wait_replies(1);
                3:    wait_replies(17);
                4:    wait_replies(160 * 120 * 2);
                default: ;
            endcase
            i += need;
        end
        repeat (100) @(posedge clk);
        $fclose(fd);
        $display("tb_top: sent %0d scene bytes, received %0d bytes, LED[3:1]=%b", len, received, led[3:1]);
        $finish;
    end
endmodule
