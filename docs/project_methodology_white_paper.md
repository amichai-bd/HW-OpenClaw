# HW-OpenClaw Methodology White Paper

## Purpose

HW-OpenClaw is organized as a monorepo for hardware development where repository structure, tool behavior, and generated collateral are deliberately predictable. The main goal is not only to build and verify IPs, but to do so in a way that is readable by both humans and automation. In practice, that means the repository favors explicit YAML-driven configuration, stable directory templates, thin user-facing commands, and discipline-specific source trees.

The project is designed around a simple principle: every engineering activity should have a clear home, a clear source of truth, and a clear output contract. RTL should live in RTL space, dynamic verification should live in DV space, formal verification should live in FV space, synthesis should live in synthesis space, and future physical design collateral should live in a dedicated PD space. The builder is not supposed to guess. It is supposed to read configuration, generate the exact run collateral required by downstream tools, and emit structured outputs under `workdir/`.

This philosophy matters for maintainability, but it also matters for AI-assisted engineering. An AI system is most effective when the repository clearly expresses intent. If the tree shape is consistent, file ownership is obvious, and the tool flows are declared in data rather than hidden in shell logic, then an AI agent can understand what belongs where, what is authoritative, and how to extend the repo without inventing side paths.

## Monorepo Philosophy

The repository treats the monorepo as a coordination layer across design disciplines. It is not a flat bucket of scripts. The intent is to keep a single repository where each IP follows the same expandable template and each discipline uses the same conceptual contract:

- source collateral lives under `src/`
- configuration lives under `cfg/`
- implementation code for tools lives under `tools/`
- user-facing commands live under `bin/`
- generated run collateral lives under `workdir/`

The builder is the execution engine, not the source of truth. Build step order is defined in `tools/build/build.yaml`. IP-specific locations and output layout are defined in `cfg/ip.yaml`. Environment and tool metadata are defined in `cfg/env.yaml`. Shared formal and synthesis profiles are defined in `cfg/fv.yaml` and `cfg/synth.yaml`. This split keeps responsibility clean:

- environment data answers what tools and shell-visible paths exist
- IP configuration answers what this repository contains
- workflow YAML answers what sequence of steps a flow should execute
- source trees answer where discipline-specific collateral belongs

The result is a repo where extending an existing IP or adding a new IP is primarily a configuration and template exercise, not a reverse-engineering exercise.

## Logic Design (RTL)

RTL is the logic design domain. Its responsibility is functional microarchitecture, protocol behavior, and synthesizable implementation. The standard template is:

```text
src/rtl/
├── common/
│   └── include/
└── <ip>/
    ├── code/
    ├── lint/
    └── filelist_rtl_<ip>.f
```

The `common` area exists so IPs can depend on shared generic collateral without creating accidental cross-IP dependencies. Shared macros, generic reusable includes, and eventually generic models belong there. That does not mean one IP can never use another IP. Real design hierarchies often compose smaller IPs into larger IPs. The rule is that reusable generic building blocks should live in `common/`, while cross-IP composition should be intentional and explicit through configuration, filelists, and integration boundaries rather than through ad hoc borrowing of a neighbor IP’s local implementation collateral.

Within an IP, `code/` contains the synthesizable logic, `lint/` contains lint waivers or lint-specific collateral, and the RTL filelist defines the authoritative RTL source set relative to `$MODEL_ROOT`. RTL coding style is intentionally strict: lowercase module and file names, uppercase parameters, lowercase underscore signal naming, `always_comb` and `always_ff` instead of plain `always`, and no inline initialization on `logic` declarations. This helps keep style consistent across simulation, synthesis, and formal.

## Dynamic Verification (DV)

Dynamic verification is the simulation-based verification domain. It follows a UVM-shaped structure without requiring a full UVM dependency. The project uses pure SystemVerilog and a predictable component split:

```text
src/dv/<ip>/
├── code/
│   ├── tb/
│   ├── if/
│   ├── pkg/
│   ├── env/
│   └── tests/
├── filelist/
└── regressions/
```

The philosophy is to keep `tb/` thin. The top should instantiate the DUT, connect interfaces, parse plusargs, and construct the environment. Verification intent should live below that level:

- `if/` owns DUT-facing signal structure
- `pkg/` gathers reusable DV collateral
- `env/` owns generator, driver, monitor, model, scoreboard, coverage, agent, env, and tracker
- `tests/` holds explicit YAML test descriptions
- `regressions/` holds explicit YAML regression definitions

This makes the DV environment expandable across multiple IPs without changing the conceptual model. It also keeps test selection explicit. The builder does not search for tests. It reads YAML, resolves paths from `cfg/ip.yaml`, and runs exactly what was requested.

Each test run emits structured artifacts under `workdir/<tag>/<ip>/tests/<test>/` or the regression equivalent. Those artifacts include at minimum simulation logs, tracker JSON, and optional VCD waveforms. That is important because debug is not treated as an afterthought. The `build -debug` flow simply discovers structured wave artifacts that were already emitted in a standard place.

## Formal Verification (FV)

Formal verification is a separate discipline, not a simulation add-on. Its tree is intentionally distinct:

```text
src/fv/
├── common/
│   ├── assumptions/
│   └── scripts/
└── <ip>/
    ├── code/
    ├── properties/
    └── proofs/
```

This separation reflects methodology. Shared assumptions and SBY scripts belong in `common/`. IP-local formal environment code belongs in `code/`. Assertions and properties belong in `properties/`. Thin proof wrappers that assemble a specific proof target belong in `proofs/`.

The formal flow is profile-driven. `cfg/fv.yaml` defines reusable proof profiles such as full `prove` or bounded `bmc`. `cfg/ip.yaml` selects the profile, the proof top, and the per-IP formal filelist for each IP. This is important because not every IP should use the same formal strategy. Simple control IPs may support a stronger full proof, while stateful data-path IPs may start with a bounded safety profile at a reduced parameter point. That is not a weakness. It is an honest formal methodology choice.

The repo already demonstrates why this separation matters. Formal on the `<IP>` exposed a real microarchitectural issue in occupancy handling during simultaneous valid push and pop. That bug was corrected in RTL and then revalidated through DV, synthesis, and formal. This is exactly the intended interaction between disciplines: formal is allowed to find real design bugs, but any RTL fix must be clean across the rest of the repository.

## Synthesis

Synthesis is treated as its own implementation discipline:

```text
src/syn/
└── common/
    ├── lib/
    └── scripts/
```

The current synthesis flow is a foundation-level Yosys flow, not a signoff flow. Shared scripts and generic liberty collateral live in `src/syn/common/`, while synthesis behavior is selected per IP through `cfg/ip.yaml` and defined by profile in `cfg/synth.yaml`.

This split keeps the synthesis domain honest. The builder prepares explicit generated filelists for tools that need absolute paths, renders a run-specific synthesis script, runs Yosys, and emits both raw reports and a derived `synth_summary.yaml`. The raw reports are preserved because they are the engineering truth. The summary exists because automation should not scrape text logs.

The same pattern will scale to richer synthesis later: technology-specific profiles, constraints, and implementation strategy changes can all live as reusable data and source collateral without changing the core repository contract.

## Physical Design

Physical design is not yet implemented as a full flow, but the methodology already suggests its place. It should become a first-class discipline, likely under `src/pd/` or a similarly explicit top-level domain, with shared collateral, per-IP setup, and YAML-driven flow selection just like FV and synthesis.

The important philosophical point is that physical design should not be bolted onto RTL or synthesis directories. It deserves its own source space because its artifacts, constraints, floorplan data, and tool strategies are a different engineering domain. When that discipline is added, it should follow the same monorepo rules:

- explicit source location
- explicit config ownership
- explicit generated run outputs
- reusable shared collateral
- per-IP selection through YAML

## Why This Structure Works

This repository is opinionated by design. It prefers explicit structure over convenience shortcuts, because explicit structure compounds over time. A new IP can be added by following existing templates. A new flow can be added by defining YAML, source collateral, and output layout instead of inventing special-case shell logic. A human can review the tree and understand ownership. An AI agent can review the same tree and reason correctly about how to extend it.

That is the real philosophy of HW-OpenClaw: a coherent hardware monorepo where design intent, verification intent, implementation intent, and generated run collateral are all kept separate but connected through stable contracts. The value is not only that the current flows work. The value is that the repository is being shaped so future IPs, future tools, and future automation can work in the same disciplined way.
