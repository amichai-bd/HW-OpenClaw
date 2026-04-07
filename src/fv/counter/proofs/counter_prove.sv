module counter_prove (
    input logic clk,
    input logic inc,
    input logic dec
);

    localparam int WIDTH = 4;

    logic rst_n;
    logic f_past_valid;
    logic [WIDTH-1:0] count;
    logic at_max;
    logic at_zero;

    counter_fv_env #(
        .WIDTH(WIDTH)
    ) u_env (
        .clk(clk),
        .inc(inc),
        .dec(dec),
        .rst_n(rst_n),
        .f_past_valid(f_past_valid),
        .count(count),
        .at_max(at_max),
        .at_zero(at_zero)
    );

    counter_properties #(
        .WIDTH(WIDTH)
    ) u_properties (
        .clk(clk),
        .rst_n(rst_n),
        .f_past_valid(f_past_valid),
        .inc(inc),
        .dec(dec),
        .count(count),
        .at_max(at_max),
        .at_zero(at_zero)
    );

endmodule
