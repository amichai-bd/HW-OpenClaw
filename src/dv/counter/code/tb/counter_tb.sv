module counter_tb;
    localparam int WIDTH = 4;
    localparam logic [WIDTH-1:0] MAX_VALUE = {WIDTH{1'b1}};

    logic clk = 0;
    logic rst_n = 0;
    logic inc = 0;
    logic dec = 0;
    logic [WIDTH-1:0] count;
    logic at_max;
    logic at_zero;

    string test_name;
    string tracker_path;
    int idx;

    `include "counter_tracker.svh"

    counter #(.WIDTH(WIDTH)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .inc(inc),
        .dec(dec),
        .count(count),
        .at_max(at_max),
        .at_zero(at_zero)
    );

    always #5 clk = ~clk;

    task automatic apply_reset();
    begin
        rst_n = 0;
        inc = 0;
        dec = 0;
        repeat (2) @(posedge clk);
        #1;
        tracker_seed_flags();
        rst_n = 1;
        #1;
        tracker_sample_flags();
    end
    endtask

    task automatic drive_inc(input logic [WIDTH-1:0] expected_value);
    begin
        inc = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("inc", count);
        tracker_sample_flags();
        if (count !== expected_value) begin
            $error("COUNTER mismatch after inc: expected %0d got %0d", expected_value, count);
        end
        inc = 1'b0;
    end
    endtask

    task automatic drive_dec(input logic [WIDTH-1:0] expected_value);
    begin
        dec = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("dec", count);
        tracker_sample_flags();
        if (count !== expected_value) begin
            $error("COUNTER mismatch after dec: expected %0d got %0d", expected_value, count);
        end
        dec = 1'b0;
    end
    endtask

    task automatic run_sanity();
    begin
        drive_inc(1);
        drive_dec(0);
        if (!at_zero) begin
            $error("COUNTER did not return to zero");
        end
    end
    endtask

    task automatic run_back_to_back();
    begin
        drive_inc(1);
        drive_inc(2);
        drive_inc(3);
        drive_dec(2);
        drive_dec(1);
        drive_dec(0);
    end
    endtask

    task automatic run_saturate_max();
    begin
        for (idx = 1; idx <= MAX_VALUE; idx++) begin
            drive_inc(idx[WIDTH-1:0]);
        end
        if (!at_max) begin
            $error("COUNTER did not assert at_max");
        end

        inc = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("inc", count);
        tracker_sample_flags();
        if (count !== MAX_VALUE) begin
            $error("COUNTER overflowed past max");
        end
        inc = 1'b0;
    end
    endtask

    task automatic run_zero_guard();
    begin
        dec = 1'b1;
        @(posedge clk);
        #1;
        tracker_emit_data("dec", count);
        tracker_sample_flags();
        if (count !== '0) begin
            $error("COUNTER decremented below zero");
        end
        dec = 1'b0;

        drive_inc(1);
        drive_dec(0);
        if (!at_zero) begin
            $error("COUNTER lost zero indication");
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

        tracker_open(tracker_path);
        apply_reset();

        case (test_name)
            "sanity": run_sanity();
            "back_to_back": run_back_to_back();
            "saturate_max": run_saturate_max();
            "zero_guard": run_zero_guard();
            default: begin
                $error("Unknown test '%s'", test_name);
            end
        endcase

        $display("test=%s count=%0d at_max=%0b at_zero=%0b", test_name, count, at_max, at_zero);
        tracker_close();
        $finish;
    end
endmodule
