module fifo_tb;
    localparam int WIDTH = 8;
    localparam int DEPTH = 4;

    logic clk = 0;
    logic rst_n = 0;
    logic push = 0;
    logic pop = 0;
    logic [WIDTH-1:0] din = '0;
    logic [WIDTH-1:0] dout;
    logic full;
    logic empty;
    logic [WIDTH-1:0] test_vec [0:DEPTH-1];
    int idx;

    `include "fifo_tracker.svh"

    fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .push(push),
        .pop(pop),
        .din(din),
        .dout(dout),
        .full(full),
        .empty(empty)
    );

    always #5 clk = ~clk;

    initial begin
        test_vec[0] = 8'h11;
        test_vec[1] = 8'h22;
        test_vec[2] = 8'h33;
        test_vec[3] = 8'h44;

        tracker_open("fifo_tracker.json");

        repeat (2) @(posedge clk);
        #1;
        tracker_seed_flags();
        rst_n = 1;

        for (idx = 0; idx < DEPTH; idx++) begin
            din = test_vec[idx];
            push = 1'b1;
            @(posedge clk);
            #1;
            tracker_emit_data("push", din);
            tracker_sample_flags();
            push = 1'b0;
        end

        if (!full) begin
            $error("FIFO did not assert full after %0d pushes", DEPTH);
        end

        for (idx = 0; idx < DEPTH; idx++) begin
            pop = 1'b1;
            @(posedge clk);
            #1;
            tracker_emit_data("pop", dout);
            tracker_sample_flags();
            if (dout !== test_vec[idx]) begin
                $error("FIFO mismatch at index %0d: expected %0h got %0h", idx, test_vec[idx], dout);
            end
            pop = 1'b0;
        end

        if (!empty) begin
            $error("FIFO did not assert empty after %0d pops", DEPTH);
        end

        $display("dout=%0h full=%0b empty=%0b", dout, full, empty);
        tracker_close();
        $finish;
    end
endmodule
