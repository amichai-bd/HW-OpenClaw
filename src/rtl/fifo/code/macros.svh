`ifndef FIFO_MACROS_SVH
`define FIFO_MACROS_SVH

`define DFF(q, d) always_ff @(posedge clk) begin q <= d; end
`define DFF_EN(q, d, en) always_ff @(posedge clk) begin if (en) q <= d; end
`define DFF_RST(q, d, rst) always_ff @(posedge clk or negedge rst) begin if (!rst) q <= '0; else q <= d; end
`define DFF_RST_VAL(q, d, rst, val) always_ff @(posedge clk or negedge rst) begin if (!rst) q <= val; else q <= d; end

`endif
