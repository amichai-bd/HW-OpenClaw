typedef enum int {
    COUNTER_TEST_SANITY,
    COUNTER_TEST_BACK_TO_BACK,
    COUNTER_TEST_SATURATE_MAX,
    COUNTER_TEST_ZERO_GUARD
} counter_test_kind_t;

typedef struct packed {
    logic [3:0] value;
} counter_txn_t;
