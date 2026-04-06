typedef enum int {
    FIFO_TEST_SANITY,
    FIFO_TEST_BACK_TO_BACK,
    FIFO_TEST_BACK_PRESSURE,
    FIFO_TEST_EMPTY_GUARD
} fifo_test_kind_t;

typedef struct packed {
    logic [7:0] data;
} fifo_txn_t;
