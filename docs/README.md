# Praxis Documentation

Production Incident Response Training Ground for AI Agents.

---

## Documentation Index

| Guide | Description |
|---|---|
| [Getting Started](./getting-started.md) | Install, run, and call your first episode in 5 minutes |
| [Action Space](./action-space.md) | All commands the agent can send |
| [Observation Space](./observation-space.md) | All fields the agent receives |
| [Tasks & Difficulty](./tasks.md) | The 3 scenarios — easy, medium, hard |
| [Reward Function](./reward-function.md) | How scoring works, what's rewarded and penalized |
| [API Reference](./api-reference.md) | HTTP endpoint specs — `/reset`, `/step`, `/state` |
| [Configuration](./configuration.md) | Environment variables, deployment settings |
| [Contributing](./contributing.md) | How to add scenarios, submit fixes, run tests |

---

## What is Praxis?

Praxis is an [OpenEnv](https://github.com/meta-pytorch/openenv)-compatible reinforcement learning environment that trains AI agents to handle production incidents — the same work SRE and on-call engineers do every day.

An agent connected to Praxis receives **incident alerts**, **system dashboards**, **logs**, and **metrics**, then must investigate, diagnose, and remediate — or escalate if the situation exceeds its confidence.

### Why This Matters

Every tech company running production services needs engineers on-call 24/7 to handle incidents. Training agents to assist — or one day replace — human on-call engineers is one of the highest-value applications of AI in infrastructure automation.

Praxis provides:
- **3 tasks** spanning easy (single service, obvious cause) to hard (ambiguous, multi-service, infrastructure-layer)
- **Dense reward signals** that reward investigation quality, diagnosis accuracy, and remediation correctness
- **Genuine difficulty** — the hard task exposes real gaps in frontier model reasoning
