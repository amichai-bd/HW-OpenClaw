module counter_fv_env #(
    parameter int WIDTH = 4
) (
    input  logic             clk,
    input  logic             inc,
    input  logic             dec,
    output logic             rst_n,
    output logic             f_past_valid,
    output logic [WIDTH-1:0] count,
    output logic             at_max,
    output logic             at_zero
);

    counter #(
        .WIDTH(WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .inc(inc),
        .dec(dec),
        .count(count),
        .at_max(at_max),
        .at_zero(at_zero)
    );

    fv_reset_ctrl u_reset_ctrl (
        .clk(clk),
        .rst_n(rst_n),
        .f_past_valid(f_past_valid)
    );

endmodule
