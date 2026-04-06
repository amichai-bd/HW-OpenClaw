interface counter_if #(
    parameter WIDTH = 4
) ();
    logic clk;
    logic rst_n;
    logic inc;
    logic dec;
    logic [WIDTH-1:0] count;
    logic at_max;
    logic at_zero;
endinterface
