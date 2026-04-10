# rtl common

This area specifies shared RTL collateral used across more than one IP.

Current contents:

- shared include files such as macros

Expected future contents:

- shared assertion macros
- generic reusable models
- common helpers that belong to the RTL discipline rather than to one IP

Rules:

- if collateral is genuinely reusable and not owned by one IP, place it here
- if a larger IP intentionally instantiates a smaller IP, that composition should be explicit in filelists and config rather than hidden through borrowed local includes

Shared RTL collateral should live here instead of inside one IP tree.
