# Git Workflows & Merge Strategies

## Quick Comparison

| Workflow | Branches | Complexity | Best For |
|----------|----------|------------|----------|
| **Gitflow** | main, develop, feature/*, release/*, hotfix/* | High | Scheduled releases |
| **GitHub Flow** | main, feature/* | Low | Continuous deployment |
| **GitLab Flow** | main, staging, production | Medium | Environment promotion |
| **Trunk-Based** | main only | Lowest | Mature CI/CD teams |
| **Forking** | fork + upstream | Medium | Open source |
| **Centralized** | main only | Simplest | Small teams, learning |

---

## 1. Gitflow (Complex)

The most structured workflow with dedicated branches for features, releases, and hotfixes.

### Branch Structure

```
main         ← Production-ready code (long-lived)
  │
  └── develop    ← Integration branch (long-lived)
        │
        ├── feature/*  ← New features (short-lived)
        │
        ├── release/*  ← Release preparation (short-lived)
        │
        └── hotfix/*   ← Emergency fixes (short-lived)
```

### Visual Flow

```
main:       ●─────────────────────●─────────●
                                  ↑         ↑
release:                 ●───●          │
                        /    \         │
develop:  ●────●────●────●──────●─────────●
               ↑    ↑          ↑
feature:       ●────●          │
                               │
hotfix:                             ●────●
                                    (from main)
```

### Merge Rules

| Branch | Created FROM | Merges TO |
|--------|--------------|-----------|
| feature/* | develop | develop |
| release/* | develop | main + develop |
| hotfix/* | main | main + develop |

### Commands

```bash
# Feature workflow
git checkout develop
git checkout -b feature/snmp-monitoring
# ... work on feature ...
git checkout develop
git merge feature/snmp-monitoring
git branch -d feature/snmp-monitoring

# Release workflow
git checkout develop
git checkout -b release/v1.0
# ... final testing, version bump ...
git checkout main
git merge release/v1.0
git tag -a v1.0 -m "Release v1.0"
git checkout develop
git merge release/v1.0

# Hotfix workflow
git checkout main
git checkout -b hotfix/critical-bug
# ... fix the bug ...
git checkout main
git merge hotfix/critical-bug
git checkout develop
git merge hotfix/critical-bug
```

---

## 2. GitHub Flow (Simple)

Lightweight workflow with only main and feature branches.

### Visual Flow

```
main:      ●────●────●────●────●────●
                \        /    \    /
feature:        ●──────●      ●──●
                    ↓           ↓
              Pull Request  Pull Request
```

### Commands

```bash
git checkout main
git checkout -b feature/new-api
git commit -am "Add new API endpoint"
git push origin feature/new-api
# Create Pull Request on GitHub
# After review, merge via PR
git checkout main
git pull origin main
git branch -d feature/new-api
```

---

## 3. GitLab Flow (Medium)

Environment-based workflow that promotes code through staging environments.

### Visual Flow

```
main:        ●────●────●────●
                       │
staging:           └────●────●
                            │
production:              └────●
```

### Commands

```bash
git checkout main
git merge feature/api
git checkout staging
git merge main
# After testing
git checkout production
git merge staging
```

---

## 4. Trunk-Based Development (Simplest)

Everyone commits directly to main. Requires feature flags.

### Visual Flow

```
main:  ●──●──●──●──●──●──●──●──●
        ↑  ↑  ↑  ↑  ↑  ↑  ↑  ↑
       All developers commit directly
       (use feature flags to hide incomplete work)
```

### Feature Flags Example

```python
FEATURE_FLAGS = {
    "new_checkout": False,  # Hidden
    "dark_mode": True,      # Visible
}

if FEATURE_FLAGS["new_checkout"]:
    show_new_checkout()
else:
    show_old_checkout()
```

---

## 5. Forking Workflow (Open Source)

Contributors fork the repository and submit Pull Requests to upstream.

### Visual Flow

```
upstream/main:     ●────●────●────●
                                   ↑
                              Pull Request
                                   │
your-fork/main:    ●────●────●
                         ↑
your-fork/feature: ●────●
```

### Commands

```bash
git clone https://github.com/YOUR-USER/repo.git
git remote add upstream https://github.com/ORIGINAL/repo.git
git checkout -b feature/fix-bug
git push origin feature/fix-bug
# Create Pull Request to upstream
git fetch upstream
git checkout main
git merge upstream/main
```

---

## 6. Centralized Workflow (Simplest)

Everyone commits directly to main. Like SVN.

```
main:  ●──●──●──●──●──●──●──●
        ↑  ↑  ↑  ↑  ↑  ↑  ↑  ↑
      Alice Bob Carol Alice Bob Carol
```

---

## Git Merge Strategies

| Strategy | Rename Support | Use Case |
|----------|----------------|----------|
| `ort` | ✓ Yes | Default for 2 branches |
| `recursive` | ✓ Yes | Synonym for ort (v2.50+) |
| `subtree` | ✓ Yes | Merge into subdirectory |
| `resolve` | ✗ No | Simple 3-way merge |
| `octopus` | ✗ No | Merge 3+ branches |
| `ours` | ✗ No | Ignore other branch entirely |

### Strategy vs Option

```bash
# Strategy OPTIONS (-X) vs Strategy (-s)
git merge -X ours feature    # Option: favor our changes in conflicts
git merge -s ours feature    # Strategy: ignore other branch entirely!
```

### Rename Files

```bash
# Correct command (git rename does NOT exist!)
git mv old_name.py new_name.py
git commit -m "Rename file"

# View history including before rename
git log --follow new_name.py
```

---

## Summary

| Workflow | Feature From | Hotfix Support | Feature Flags |
|----------|--------------|----------------|---------------|
| Gitflow | develop | ✓ hotfix/* | Not needed |
| GitHub Flow | main | via feature branch | Common |
| GitLab Flow | main | via environment | Optional |
| Trunk-Based | main (direct) | direct commit | Required |
| Forking | fork/main | via PR | Optional |
| Centralized | main (direct) | direct commit | Optional |