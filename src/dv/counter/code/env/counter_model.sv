function automatic counter_txn_t counter_expected_txn(input int value);
    counter_txn_t txn;

    txn.value = value[3:0];
    return txn;
endfunction
