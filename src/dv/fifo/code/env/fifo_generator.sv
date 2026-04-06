function automatic fifo_cfg_t fifo_build_cfg(input string test_name);
    fifo_cfg_t cfg;

    cfg.test_name = test_name;
    case (test_name)
        "sanity": cfg.kind = FIFO_TEST_SANITY;
        "back_to_back": cfg.kind = FIFO_TEST_BACK_TO_BACK;
        "back_pressure": cfg.kind = FIFO_TEST_BACK_PRESSURE;
        "empty_guard": cfg.kind = FIFO_TEST_EMPTY_GUARD;
        default: begin
            cfg.kind = FIFO_TEST_SANITY;
            $fatal(1, "Unknown test '%s'", test_name);
        end
    endcase

    return cfg;
endfunction
