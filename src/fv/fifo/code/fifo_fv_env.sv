module fifo_fv_env #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 4
) (
    input  logic                 clk,
    input  logic                 push,
    input  logic                 pop,
    input  logic [WIDTH-1:0]     din,
    output logic                 rst_n,
    output logic                 f_past_valid,
    output logic [WIDTH-1:0]     dout,
    output logic                 full,
    output logic                 empty,
    output logic [$clog2(DEPTH + 1)-1:0] shadow_count
);

    localparam int COUNT_W = $clog2(DEPTH + 1);

    fifo #(
        .WIDTH(WIDTH),
        .DEPTH(DEPTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .push(push),
        .pop(pop),
        .din(din),
        .dout(dout),
        .full(full),
        .empty(empty)
    );

    fv_reset_ctrl u_reset_ctrl (
        .clk(clk),
        .rst_n(rst_n),
        .f_past_valid(f_past_valid)
    );

    initial begin
        assume(shadow_count == '0);
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            shadow_count <= '0;
        end else begin
            if (push && !full && !(pop && !empty)) begin
                shadow_count <= shadow_count + COUNT_W'(1);
            end else if (pop && !empty && !(push && !full)) begin
                shadow_count <= shadow_count - COUNT_W'(1);
            end
        end
    end

endmodule
