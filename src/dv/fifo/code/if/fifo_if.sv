interface fifo_if #(
    parameter WIDTH = 8
) ();
    logic clk;
    logic rst_n;
    logic push;
    logic pop;
    logic [WIDTH-1:0] din;
    logic [WIDTH-1:0] dout;
    logic full;
    logic empty;
endinterface
