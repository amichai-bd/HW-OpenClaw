module FIFO #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 4
) (
    input  logic                  clk,
    input  logic                  rst_n,
    input  logic                  push,
    input  logic                  pop,
    input  logic [WIDTH-1:0]      din,
    output logic [WIDTH-1:0]      dout,
    output logic                  full,
    output logic                  empty
);

    logic [WIDTH-1:0] mem [DEPTH];
    int unsigned wr_ptr;
    int unsigned rd_ptr;
    int unsigned count;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            count  <= 0;
            dout   <= '0;
        end else begin
            if (push && !full) begin
                mem[wr_ptr] <= din;
                wr_ptr <= (wr_ptr + 1) % DEPTH;
                count  <= count + 1;
            end

            if (pop && !empty) begin
                dout   <= mem[rd_ptr];
                rd_ptr <= (rd_ptr + 1) % DEPTH;
                count  <= count - 1;
            end
        end
    end

endmodule
