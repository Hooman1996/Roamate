# Working on Roamate

This file is for anyone, human or coding agent, who changes this repository. It summarizes the rules in [the implementation plan](docs/plan/implementation-plan.md) §0 and §13.

## Which document wins

1. hooman's latest written decision (in the plan or in `docs/adr/`).
2. [docs/plan/implementation-plan.md](docs/plan/implementation-plan.md), latest approved version: scope, order, limits, release gates.
3. `docs/design/*`: the contract of one component. Check its status block. A `draft` is not a contract.
4. [docs/plan/implementation-steps.md](docs/plan/implementation-steps.md): what is done.
5. `docs/plan/roadmap.html` is generated. Never edit it by hand. Run `python scripts/build_roadmap.py` after changing the plan or the steps.
6. `docs/background/*` is history. `solver_example.py` is an illustration with known issues listed in its header.

## How a step is done

1. Its design is approved (status block says `approved`).
2. Post a short step brief and wait for hooman's go-ahead. The brief names the design it follows, what will be built, the files that change, the acceptance command, the tests, and any detail the design left open.
3. Pull the latest `main` first. Until Web Alpha, commit directly to `main`, one person or agent pushing at a time. From Web Alpha on, use a branch named after the step (`m11-2-stop-locks`) and a pull request.
4. Tests and CI must be green before the next step starts.
5. Tick the step with evidence: `- [x] **M1.3** … (done: <commit>, <test or command>)`, then regenerate the roadmap.
6. If coding shows the design is wrong, stop and propose a change to the design. The code follows the approved design.

M0 spike steps (M0.15, M0.16) write throwaway code to answer a design question. It is not product code.

## Shared services (RagBot)

- Never stop, restart or reconfigure a RagBot container (Postgres, Qdrant, MinIO, TEI, vLLM). Failure tests use fake providers or a wrong Roamate address.
- Only touch databases, roles, collections and buckets whose names start with `roamate`. Setup scripts are dry-run unless `--apply` is given.
- Embedding experiments use `roamate-tei-lab`, never RagBot's TEI.
- Keep to the request caps in `.env` (`VLLM_MAX_PARALLEL`, `TEI_MAX_PARALLEL`).

## Always

- Secrets only in `.env`, never committed. `.env.example` lists every setting without values.
- LLM output is a Pydantic model and is checked before use. Only code writes trip state. Every number the user sees comes from the solver or the budget calculator.
- Never present estimated or unknown data as checked.
- No model identifiers in commits, pull requests or code comments.
