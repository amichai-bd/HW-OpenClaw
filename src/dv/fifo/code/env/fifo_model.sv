function automatic fifo_txn_t fifo_expected_txn(input int index);
    fifo_txn_t txn;

    case (index)
        0: txn.data = 8'h11;
        1: txn.data = 8'h22;
        2: txn.data = 8'h33;
        3: txn.data = 8'h44;
        default: txn.data = 8'h00;
    endcase

    return txn;
endfunction
