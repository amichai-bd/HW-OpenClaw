module fifo_tb;
    localparam int WIDTH = 8;
    localparam int DEPTH = 4;

    import fifo_dv_pkg::*;

    fifo_if #(.WIDTH(WIDTH)) vif ();
    fifo_cfg_t cfg;
    fifo_txn_t expected_txn;
    string tracker_path;
    string test_name;
    int idx;

    `include "fifo_tracker.svh"

    fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(vif.clk),
        .rst_n(vif.rst_n),
        .push(vif.push),
        .pop(vif.pop),
        .din(vif.din),
        .dout(vif.dout),
        .full(vif.full),
        .empty(vif.empty)
    );

    initial vif.clk = 0;
    always #5 vif.clk = ~vif.clk;

    task automatic apply_reset();
    begin
        vif.rst_n = 0;
        vif.push = 0;
        vif.pop = 0;
        vif.din = '0;
        repeat (2) @(posedge vif.clk);
        #1;
        tracker_seed_flags();
        vif.rst_n = 1;
        #1;
        tracker_sample_flags();
    end
    endtask

    task automatic drive_push(input logic [WIDTH-1:0] value);
    begin
        vif.din = value;
        vif.push = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("push", value);
        tracker_sample_flags();
        vif.push = 1'b0;
    end
    endtask

    task automatic drive_pop(input logic [WIDTH-1:0] expected_value);
    begin
        vif.pop = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("pop", vif.dout);
        tracker_sample_flags();
        if (vif.dout !== expected_value) begin
            $error("FIFO mismatch: expected %0h got %0h", expected_value, vif.dout);
        end
        vif.pop = 1'b0;
    end
    endtask

    task automatic run_sanity();
    begin
        expected_txn = fifo_expected_txn(0);
        drive_push(expected_txn.data);
        if (vif.empty) begin
            $error("FIFO stayed empty after one push");
        end
        drive_pop(expected_txn.data);
        if (!vif.empty) begin
            $error("FIFO did not return to empty after sanity pop");
        end
    end
    endtask

    task automatic run_back_to_back();
    begin
        for (idx = 0; idx < DEPTH; idx++) begin
            expected_txn = fifo_expected_txn(idx);
            drive_push(expected_txn.data);
        end

        if (!vif.full) begin
            $error("FIFO did not assert full after %0d pushes", DEPTH);
        end

        for (idx = 0; idx < DEPTH; idx++) begin
            expected_txn = fifo_expected_txn(idx);
            drive_pop(expected_txn.data);
        end

        if (!vif.empty) begin
            $error("FIFO did not assert empty after %0d pops", DEPTH);
        end
    end
    endtask

    task automatic run_back_pressure();
        logic [WIDTH-1:0] blocked_value;
    begin
        blocked_value = 8'hee;

        for (idx = 0; idx < DEPTH; idx++) begin
            expected_txn = fifo_expected_txn(idx);
            drive_push(expected_txn.data);
        end

        if (!vif.full) begin
            $error("FIFO did not assert full before blocked push");
        end

        drive_push(blocked_value);

        if (!vif.full) begin
            $error("FIFO lost full during blocked push");
        end

        for (idx = 0; idx < DEPTH; idx++) begin
            expected_txn = fifo_expected_txn(idx);
            drive_pop(expected_txn.data);
        end

        if (!vif.empty) begin
            $error("FIFO did not empty after blocked push scenario");
        end
    end
    endtask

    task automatic run_empty_guard();
    begin
        vif.pop = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("pop", vif.dout);
        tracker_sample_flags();
        vif.pop = 1'b0;

        if (!vif.empty) begin
            $error("FIFO lost empty after pop on empty");
        end

        expected_txn = fifo_expected_txn(1);
        drive_push(expected_txn.data);
        drive_pop(expected_txn.data);

        if (!vif.empty) begin
            $error("FIFO did not return to empty in empty_guard");
        end
    end
    endtask

    initial begin
        test_name = "sanity";
        tracker_path = "";
        void'($value$plusargs("test=%s", test_name));
        if (!$value$plusargs("tracker_path=%s", tracker_path)) begin
            $fatal(1, "missing +tracker_path");
        end
        cfg = fifo_build_cfg(test_name);

        tracker_open(tracker_path);
        apply_reset();

        case (cfg.kind)
            FIFO_TEST_SANITY: run_sanity();
            FIFO_TEST_BACK_TO_BACK: run_back_to_back();
            FIFO_TEST_BACK_PRESSURE: run_back_pressure();
            FIFO_TEST_EMPTY_GUARD: run_empty_guard();
            default: $fatal(1, "Unsupported test kind");
        endcase

        $display("test=%s dout=%0h full=%0b empty=%0b", test_name, vif.dout, vif.full, vif.empty);
        tracker_close();
        $finish;
    end
endmodule
