# Project rules

## Branching — HARD RULE
- **NEVER merge or push anything to `main` on GitHub.** `main` is the dad's authoritative branch (he wrote the original program). Treat it as read-only.
- The user works on branch **`ro`**. All feature branches merge into **`ro`**, never `main`.
- Committing on feature branches and on `ro` is fine. Do not target `main` with merge/push/PR without an explicit, fresh instruction for that specific action.
