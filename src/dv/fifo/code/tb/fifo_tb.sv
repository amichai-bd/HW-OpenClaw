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
    string tracker_path;
    string test_name;
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

    task automatic seed_test_vec();
    begin
        test_vec[0] = 8'h11;
        test_vec[1] = 8'h22;
        test_vec[2] = 8'h33;
        test_vec[3] = 8'h44;
    end
    endtask

    task automatic apply_reset();
    begin
        rst_n = 0;
        push = 0;
        pop = 0;
        din = '0;
        repeat (2) @(posedge clk);
        #1;
        tracker_seed_flags();
        rst_n = 1;
        #1;
        tracker_sample_flags();
    end
    endtask

    task automatic drive_push(input logic [WIDTH-1:0] value);
    begin
        din = value;
        push = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("push", value);
        tracker_sample_flags();
        push = 1'b0;
    end
    endtask

    task automatic drive_pop(input logic [WIDTH-1:0] expected_value);
    begin
        pop = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("pop", dout);
        tracker_sample_flags();
        if (dout !== expected_value) begin
            $error("FIFO mismatch: expected %0h got %0h", expected_value, dout);
        end
        pop = 1'b0;
    end
    endtask

    task automatic run_sanity();
    begin
        drive_push(test_vec[0]);
        if (empty) begin
            $error("FIFO stayed empty after one push");
        end
        drive_pop(test_vec[0]);
        if (!empty) begin
            $error("FIFO did not return to empty after sanity pop");
        end
    end
    endtask

    task automatic run_back_to_back();
    begin
        for (idx = 0; idx < DEPTH; idx++) begin
            drive_push(test_vec[idx]);
        end

        if (!full) begin
            $error("FIFO did not assert full after %0d pushes", DEPTH);
        end

        for (idx = 0; idx < DEPTH; idx++) begin
            drive_pop(test_vec[idx]);
        end

        if (!empty) begin
            $error("FIFO did not assert empty after %0d pops", DEPTH);
        end
    end
    endtask

    task automatic run_back_pressure();
        logic [WIDTH-1:0] blocked_value;
    begin
        blocked_value = 8'hee;

        for (idx = 0; idx < DEPTH; idx++) begin
            drive_push(test_vec[idx]);
        end

        if (!full) begin
            $error("FIFO did not assert full before blocked push");
        end

        drive_push(blocked_value);

        if (!full) begin
            $error("FIFO lost full during blocked push");
        end

        for (idx = 0; idx < DEPTH; idx++) begin
            drive_pop(test_vec[idx]);
        end

        if (!empty) begin
            $error("FIFO did not empty after blocked push scenario");
        end
    end
    endtask

    task automatic run_empty_guard();
    begin
        pop = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("pop", dout);
        tracker_sample_flags();
        pop = 1'b0;

        if (!empty) begin
            $error("FIFO lost empty after pop on empty");
        end

        drive_push(test_vec[1]);
        drive_pop(test_vec[1]);

        if (!empty) begin
            $error("FIFO did not return to empty in empty_guard");
        end
    end
    endtask

    initial begin
        seed_test_vec();
        test_name = "sanity";
        tracker_path = "";
        void'($value$plusargs("test=%s", test_name));
        if (!$value$plusargs("tracker_path=%s", tracker_path)) begin
            $fatal(1, "missing +tracker_path");
        end

        tracker_open(tracker_path);
        apply_reset();

        case (test_name)
            "sanity": run_sanity();
            "back_to_back": run_back_to_back();
            "back_pressure": run_back_pressure();
            "empty_guard": run_empty_guard();
            default: begin
                $error("Unknown test '%s'", test_name);
            end
        endcase

        $display("test=%s dout=%0h full=%0b empty=%0b", test_name, dout, full, empty);
        tracker_close();
        $finish;
    end
endmodule
