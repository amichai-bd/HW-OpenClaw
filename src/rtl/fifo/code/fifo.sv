`include "macros.svh"

module fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 4
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 push,
    input  logic                 pop,
    input  logic [WIDTH-1:0]     din,
    output logic [WIDTH-1:0]     dout,
    output logic                 full,
    output logic                 empty
);

    localparam int PTR_W   = $clog2(DEPTH);
    localparam int COUNT_W = $clog2(DEPTH + 1);

    logic [WIDTH-1:0] mem [DEPTH];
    logic [WIDTH-1:0] mem_next [DEPTH];
    logic [PTR_W-1:0] wr_ptr, wr_ptr_next;
    logic [PTR_W-1:0] rd_ptr, rd_ptr_next;
    logic [COUNT_W-1:0] count, count_next;
    logic [WIDTH-1:0] dout_next;
    logic full_next;
    logic empty_next;
    logic push_ok;
    logic pop_ok;
    integer i;

    always_comb begin
        for (i = 0; i < DEPTH; i++) begin
            mem_next[i] = mem[i];
        end

        wr_ptr_next = wr_ptr;
        rd_ptr_next = rd_ptr;
        count_next   = count;
        dout_next    = dout;
        full_next    = full;
        empty_next   = empty;

        push_ok = push && !full;
        pop_ok  = pop && !empty;

        if (push_ok) begin
            mem_next[wr_ptr] = din;
            wr_ptr_next = wr_ptr + 1'b1;
            count_next   = count + 1'b1;
        end

        if (pop_ok) begin
            dout_next  = mem[rd_ptr];
            rd_ptr_next = rd_ptr + 1'b1;
            count_next  = count - 1'b1;
        end

        full_next  = (count_next == DEPTH);
        empty_next = (count_next == 0);
    end

    `DFF_RST(wr_ptr, wr_ptr_next, rst_n)
    `DFF_RST(rd_ptr, rd_ptr_next, rst_n)
    `DFF_RST(count, count_next, rst_n)
    `DFF_RST(dout, dout_next, rst_n)
    `DFF_RST_VAL(full, full_next, rst_n, 1'b0)
    `DFF_RST_VAL(empty, empty_next, rst_n, 1'b1)

    genvar g;
    generate
        for (g = 0; g < DEPTH; g++) begin : gen_mem
            `DFF_RST(mem[g], mem_next[g], rst_n)
        end
    endgenerate

endmodule
