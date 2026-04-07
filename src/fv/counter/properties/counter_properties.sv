module counter_properties #(
    parameter int WIDTH = 4
) (
    input logic             clk,
    input logic             rst_n,
    input logic             f_past_valid,
    input logic             inc,
    input logic             dec,
    input logic [WIDTH-1:0] count,
    input logic             at_max,
    input logic             at_zero
);

    localparam logic [WIDTH-1:0] MAX_VALUE = {WIDTH{1'b1}};

    function automatic logic [WIDTH-1:0] expected_count(
        input logic [WIDTH-1:0] prior_count,
        input logic             prior_inc,
        input logic             prior_dec
    );
        logic prior_at_max;
        logic prior_at_zero;
        logic inc_ok;
        logic dec_ok;
        begin
            prior_at_max = (prior_count == MAX_VALUE);
            prior_at_zero = (prior_count == '0);
            inc_ok = prior_inc && !prior_at_max;
            dec_ok = prior_dec && !prior_at_zero;

            expected_count = prior_count;
            if (inc_ok && !dec_ok) begin
                expected_count = prior_count + 1'b1;
            end else if (dec_ok && !inc_ok) begin
                expected_count = prior_count - 1'b1;
            end
        end
    endfunction

    always_ff @(posedge clk) begin
        assert(at_zero == (count == '0));
        assert(at_max == (count == MAX_VALUE));

        if (f_past_valid && !$past(rst_n)) begin
            assert(count == '0);
            assert(at_zero);
            assert(!at_max);
        end else if (f_past_valid && $past(rst_n)) begin
            assert(count == expected_count($past(count), $past(inc), $past(dec)));
        end

        cover(at_max);
        cover(f_past_valid && rst_n && $past(count) == 4'd1 && dec && !inc && at_zero);
    end

endmodule
