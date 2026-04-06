integer tracker_fd = 0;
bit tracker_first = 1'b1;
bit tracker_max_prev = 1'b0;
bit tracker_zero_prev = 1'b1;

task tracker_open(input string path);
begin
    tracker_fd = $fopen(path, "w");
    if (tracker_fd == 0) $fatal(1, "failed to open tracker file");
    tracker_first = 1'b1;
    $fwrite(tracker_fd, "[\n");
end
endtask

task tracker_emit_event(input string event_name);
begin
    if (tracker_fd == 0) $fatal(1, "tracker file is not open");
    if (!tracker_first) $fwrite(tracker_fd, ",\n");
    $fwrite(tracker_fd, "  {\"time\": %0t, \"event\": \"%s\"}", $time, event_name);
    tracker_first = 1'b0;
end
endtask

task tracker_emit_data(input string event_name, input logic [WIDTH-1:0] value);
begin
    if (tracker_fd == 0) $fatal(1, "tracker file is not open");
    if (!tracker_first) $fwrite(tracker_fd, ",\n");
    $fwrite(
        tracker_fd,
        "  {\"time\": %0t, \"event\": \"%s\", \"data\": %0d}",
        $time,
        event_name,
        value
    );
    tracker_first = 1'b0;
end
endtask

task tracker_seed_flags();
begin
    tracker_max_prev = at_max;
    tracker_zero_prev = at_zero;
end
endtask

task tracker_sample_flags();
begin
    if (!tracker_max_prev && at_max) tracker_emit_event("max");
    if (!tracker_zero_prev && at_zero) tracker_emit_event("zero");
    tracker_max_prev = at_max;
    tracker_zero_prev = at_zero;
end
endtask

task tracker_close();
begin
    if (tracker_fd != 0) begin
        $fwrite(tracker_fd, "\n]\n");
        $fclose(tracker_fd);
        tracker_fd = 0;
    end
end
endtask
