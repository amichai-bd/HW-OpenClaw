function automatic counter_cfg_t counter_build_cfg(input string test_name);
    counter_cfg_t cfg;

    cfg.test_name = test_name;
    case (test_name)
        "sanity": cfg.kind = COUNTER_TEST_SANITY;
        "back_to_back": cfg.kind = COUNTER_TEST_BACK_TO_BACK;
        "saturate_max": cfg.kind = COUNTER_TEST_SATURATE_MAX;
        "zero_guard": cfg.kind = COUNTER_TEST_ZERO_GUARD;
        default: begin
            cfg.kind = COUNTER_TEST_SANITY;
            $fatal(1, "Unknown test '%s'", test_name);
        end
    endcase

    return cfg;
endfunction
