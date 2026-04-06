module counter_tb;
    localparam int WIDTH = 4;
    localparam logic [WIDTH-1:0] MAX_VALUE = {WIDTH{1'b1}};

    import counter_dv_pkg::*;

    counter_if #(.WIDTH(WIDTH)) vif ();
    counter_cfg_t cfg;
    counter_txn_t expected_txn;
    string test_name;
    string tracker_path;
    string wave_path;
    int wave_enable;
    int idx;

    `include "counter_tracker.svh"

    counter #(.WIDTH(WIDTH)) dut (
        .clk(vif.clk),
        .rst_n(vif.rst_n),
        .inc(vif.inc),
        .dec(vif.dec),
        .count(vif.count),
        .at_max(vif.at_max),
        .at_zero(vif.at_zero)
    );

    initial vif.clk = 0;
    always #5 vif.clk = ~vif.clk;

    task automatic apply_reset();
    begin
        vif.rst_n = 0;
        vif.inc = 0;
        vif.dec = 0;
        repeat (2) @(posedge vif.clk);
        #1;
        tracker_seed_flags();
        vif.rst_n = 1;
        #1;
        tracker_sample_flags();
    end
    endtask

    task automatic drive_inc(input logic [WIDTH-1:0] expected_value);
    begin
        vif.inc = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("inc", vif.count);
        tracker_sample_flags();
        if (vif.count !== expected_value) begin
            $error("COUNTER mismatch after inc: expected %0d got %0d", expected_value, vif.count);
        end
        vif.inc = 1'b0;
    end
    endtask

    task automatic drive_dec(input logic [WIDTH-1:0] expected_value);
    begin
        vif.dec = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("dec", vif.count);
        tracker_sample_flags();
        if (vif.count !== expected_value) begin
            $error("COUNTER mismatch after dec: expected %0d got %0d", expected_value, vif.count);
        end
        vif.dec = 1'b0;
    end
    endtask

    task automatic run_sanity();
    begin
        expected_txn = counter_expected_txn(1);
        drive_inc(expected_txn.value);
        expected_txn = counter_expected_txn(0);
        drive_dec(expected_txn.value);
        if (!vif.at_zero) begin
            $error("COUNTER did not return to zero");
        end
    end
    endtask

    task automatic run_back_to_back();
    begin
        drive_inc(counter_expected_txn(1).value);
        drive_inc(counter_expected_txn(2).value);
        drive_inc(counter_expected_txn(3).value);
        drive_dec(counter_expected_txn(2).value);
        drive_dec(counter_expected_txn(1).value);
        drive_dec(counter_expected_txn(0).value);
    end
    endtask

    task automatic run_saturate_max();
    begin
        for (idx = 1; idx <= MAX_VALUE; idx++) begin
            expected_txn = counter_expected_txn(idx);
            drive_inc(expected_txn.value);
        end
        if (!vif.at_max) begin
            $error("COUNTER did not assert at_max");
        end

        vif.inc = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("inc", vif.count);
        tracker_sample_flags();
        if (vif.count !== MAX_VALUE) begin
            $error("COUNTER overflowed past max");
        end
        vif.inc = 1'b0;
    end
    endtask

    task automatic run_zero_guard();
    begin
        vif.dec = 1'b1;
        @(posedge vif.clk);
        #1;
        tracker_emit_data("dec", vif.count);
        tracker_sample_flags();
        if (vif.count !== '0) begin
            $error("COUNTER decremented below zero");
        end
        vif.dec = 1'b0;

        drive_inc(counter_expected_txn(1).value);
        drive_dec(counter_expected_txn(0).value);
        if (!vif.at_zero) begin
            $error("COUNTER lost zero indication");
        end
    end
    endtask

    initial begin
        test_name = "sanity";
        tracker_path = "";
        wave_path = "";
        wave_enable = 0;
        void'($value$plusargs("test=%s", test_name));
        if (!$value$plusargs("tracker_path=%s", tracker_path)) begin
            $fatal(1, "missing +tracker_path");
        end
        void'($value$plusargs("wave_enable=%d", wave_enable));
        void'($value$plusargs("wave_path=%s", wave_path));
        cfg = counter_build_cfg(test_name);

        if (wave_enable != 0) begin
            if (wave_path == "") begin
                $fatal(1, "missing +wave_path");
            end
            $dumpfile(wave_path);
            $dumpvars(0, counter_tb);
        end

        tracker_open(tracker_path);
        apply_reset();

        case (cfg.kind)
            COUNTER_TEST_SANITY: run_sanity();
            COUNTER_TEST_BACK_TO_BACK: run_back_to_back();
            COUNTER_TEST_SATURATE_MAX: run_saturate_max();
            COUNTER_TEST_ZERO_GUARD: run_zero_guard();
            default: $fatal(1, "Unsupported test kind");
        endcase

        $display("test=%s count=%0d at_max=%0b at_zero=%0b", test_name, vif.count, vif.at_max, vif.at_zero);
        tracker_close();
        $finish;
    end
endmodule
