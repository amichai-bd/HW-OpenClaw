module fifo_properties #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 4
) (
    input logic                     clk,
    input logic                     rst_n,
    input logic                     f_past_valid,
    input logic                     push,
    input logic                     pop,
    input logic [WIDTH-1:0]         dout,
    input logic                     full,
    input logic                     empty,
    input logic [$clog2(DEPTH + 1)-1:0] shadow_count
);

    localparam int COUNT_W = $clog2(DEPTH + 1);

    always_ff @(posedge clk) begin
        assert(full == (shadow_count == COUNT_W'(DEPTH)));
        assert(empty == (shadow_count == '0));
        assert(!(full && empty));

        if (f_past_valid && !$past(rst_n)) begin
            assert(shadow_count == '0);
            assert(dout == '0);
            assert(!full);
            assert(empty);
        end

        cover(full);
        cover(f_past_valid && rst_n && $past(shadow_count) == COUNT_W'(1) && pop && empty);
    end

endmodule
