# Praxis ops scripts

Read-only-by-default operational scripts. None of these mutate GitHub or the
repo unless you pass `--apply`.

| Script                       | What it does                                                                                                   | Idempotent?                                                        |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `create_github_issues.py`    | Reads `idea/Plan/github_issues.md` and creates/updates the 21 issues on GitHub via `gh`.                       | Yes — re-run to sync title/body/labels/assignee with the markdown. |
| `setup_branch_protection.py` | Applies the `main` branch protection rule (1 review + CODEOWNERS + CI green + linear history + no force push). | Yes — PUT semantics.                                               |
| `submit_hf_grpo_job.py`      | Preflight (`git ls-remote`) + submit a full GRPO run on HF Jobs at the local HEAD SHA.                         | Yes — re-run to launch a new job; the bootstrap pins the SHA.      |
| `run_hf_grpo_job.py`         | UV bootstrap that runs *inside* the HF Jobs container: clones Praxis at a pinned SHA and runs the trainer.     | N/A — invoked by the submitter, not by hand.                       |

## Prereqs (one-time)

```bash
gh auth login                 # authenticate with GitHub
gh auth status                # confirm "Logged in to github.com account ..."
```

## Recommended sequence

```bash
# 1. Land the workflows + plan docs first so CI starts producing the
#    required check names (Lint (ruff), Test (Python 3.11), ...).
git push origin main

# 2. Apply branch protection. The check names match ci.yml job `name:` fields.
python scripts/setup_branch_protection.py            # dry-run
python scripts/setup_branch_protection.py --apply    # apply

# 3. Open the 21 issues. Dry-run first to inspect.
python scripts/create_github_issues.py               # dry-run
python scripts/create_github_issues.py --apply       # creates everything
python scripts/create_github_issues.py --apply --only 1   # just one
```

## Submitting a full GRPO training run on HF Jobs

`scripts/submit_hf_grpo_job.py` is the production entry point for the
GPU GRPO run referenced in the production-merge checklist.

### Prereqs

- `hf auth login` (or `HF_TOKEN` exported); Pro/Team/Enterprise plan for Jobs.
- `gp5901/praxis` Space running (the trainer hits it for HTTP rollouts).
- The branch you want to run from must be pushed to `origin` so the GPU
  container can `git clone` it. The submitter enforces this with a local
  `git ls-remote` preflight before calling `hf jobs uv run`.

### One-command launch

```bash
git push origin HEAD                                  # required: trainer SHA must be on origin
python scripts/submit_hf_grpo_job.py \
  --hub-model-id gp5901/praxis-grpo-7b \
  --trackio-space-id gp5901/trackio \
  --flavor a10g-large \
  --timeout 5h
```

The submitter:

1. Resolves the local `HEAD` SHA, runs `git ls-remote` against `origin`,
   and aborts if the SHA hasn't propagated yet.
2. Computes the raw GitHub URL of `scripts/run_hf_grpo_job.py` at that SHA.
3. Calls `hf jobs uv run --flavor <flavor> --secrets HF_TOKEN --env PRAXIS_COMMIT=<SHA> ... <launcher-url>`.
4. Streams logs (default) or returns immediately with `--detach`.

Inside the container, the bootstrap clones the same SHA, runs the trainer
via `uv run train_praxis_grpo.py --learning-rate 1e-4 --group-size 8 --steps 200 ...`,
and uploads `checkpoints/praxis-grpo/{run_manifest.json,metrics.csv}` to the
Hub model repo so judges can reproduce / verify.

Use `--dry-run` to print the resolved `hf jobs uv run` command without submitting.

## Rollback

- Branch protection: `gh api -X DELETE repos/<owner>/<repo>/branches/main/protection`
- Issues: `gh issue close <num>` per number, or close them in the UI.
- HF Jobs: `hf jobs cancel <job-id>` (find it with `hf jobs ps`).

## Why generated, not hand-typed

`create_github_issues.py` reads `idea/Plan/github_issues.md` so the GitHub
issues stay in lock-step with the plan docs. Edit the markdown, re-run with
`--apply`, and the issues update. No copy-paste drift.

`setup_branch_protection.py` keeps the protection rule in code so the team
can review the policy diff like any other PR.
