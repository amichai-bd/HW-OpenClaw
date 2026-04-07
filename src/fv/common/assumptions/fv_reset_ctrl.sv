module fv_reset_ctrl #(
    parameter int RESET_CYCLES = 2
) (
    input  logic clk,
    output logic rst_n,
    output logic f_past_valid
);

    localparam int COUNT_W = (RESET_CYCLES > 1) ? $clog2(RESET_CYCLES + 1) : 1;

    logic [COUNT_W-1:0] reset_count;

    initial begin
        assume(f_past_valid == 1'b0);
        assume(reset_count == '0);
    end

    always_comb begin
        rst_n = (reset_count >= RESET_CYCLES);
    end

    always_ff @(posedge clk) begin
        f_past_valid <= 1'b1;
        if (!rst_n) begin
            reset_count <= reset_count + 1'b1;
        end

        if (!f_past_valid) begin
            assert(!rst_n);
        end
    end

endmodule
