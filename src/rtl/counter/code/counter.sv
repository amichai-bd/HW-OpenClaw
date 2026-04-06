`include "macros.svh"

module counter #(
    parameter WIDTH = 4
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             inc,
    input  logic             dec,
    output logic [WIDTH-1:0] count,
    output logic             at_max,
    output logic             at_zero
);

    localparam logic [WIDTH-1:0] MAX_VALUE = {WIDTH{1'b1}};

    logic [WIDTH-1:0] count_next;
    logic at_max_next;
    logic at_zero_next;
    logic inc_ok;
    logic dec_ok;

    always_comb begin
        count_next = count;
        at_max_next = at_max;
        at_zero_next = at_zero;

        inc_ok = inc && !at_max;
        dec_ok = dec && !at_zero;

        if (inc_ok && !dec_ok) begin
            count_next = count + 1'b1;
        end else if (dec_ok && !inc_ok) begin
            count_next = count - 1'b1;
        end

        at_max_next = (count_next == MAX_VALUE);
        at_zero_next = (count_next == '0);
    end

    `DFF_RST(count, count_next, rst_n)
    `DFF_RST_VAL(at_max, at_max_next, rst_n, 1'b0)
    `DFF_RST_VAL(at_zero, at_zero_next, rst_n, 1'b1)

endmodule
