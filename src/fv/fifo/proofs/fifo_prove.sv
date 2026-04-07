module fifo_prove (
    input logic             clk,
    input logic             push,
    input logic             pop,
    input logic [1:0]       din
);

    // Use a small parameter point to keep the formal control proof tractable.
    localparam int WIDTH = 2;
    localparam int DEPTH = 2;
    localparam int COUNT_W = $clog2(DEPTH + 1);

    logic rst_n;
    logic f_past_valid;
    logic [WIDTH-1:0] dout;
    logic full;
    logic empty;
    logic [COUNT_W-1:0] count;

    fifo_fv_env #(
        .WIDTH(WIDTH),
        .DEPTH(DEPTH)
    ) u_env (
        .clk(clk),
        .push(push),
        .pop(pop),
        .din(din),
        .rst_n(rst_n),
        .f_past_valid(f_past_valid),
        .dout(dout),
        .full(full),
        .empty(empty),
        .shadow_count(count)
    );

    fifo_properties #(
        .WIDTH(WIDTH),
        .DEPTH(DEPTH)
    ) u_properties (
        .clk(clk),
        .rst_n(rst_n),
        .f_past_valid(f_past_valid),
        .push(push),
        .pop(pop),
        .dout(dout),
        .full(full),
        .empty(empty),
        .shadow_count(count)
    );

    always_comb begin
        assume(din == '0);
    end

endmodule
