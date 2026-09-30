# Git Operations Quick Reference

## Table of Contents

| # | Command | Purpose |
|---|---------|---------|
| 1 | [git revert](#git-revert) | Undo commit safely (creates new commit) |
| 2 | [git reset](#git-reset) | Move HEAD backward, discard commits |
| 3 | [git rebase](#git-rebase) | Replay commits on another branch |
| 4 | [git cherry-pick](#git-cherry-pick) | Copy specific commit to current branch |
| 5 | [git format-patch](#git-format-patch) | Export commits as patch files |
| 6 | [git merge](#git-merge) | Combine two branches |
| 7 | [git bisect](#git-bisect) | Binary search to find buggy commit |

### Quick Comparison

| Command | Rewrites History? | Safe for Shared Branches? |
|---------|-------------------|---------------------------|
| `revert` | No | ✅ Yes |
| `reset` | Yes | ❌ No |
| `rebase` | Yes | ❌ No |
| `cherry-pick` | No | ✅ Yes |
| `format-patch` | No | ✅ Yes |
| `merge` | No | ✅ Yes |
| `bisect` | No | ✅ Yes |

---

## git revert

**Undoes a commit by creating a NEW commit that reverses the changes.**  
Safe for shared branches since it doesn't rewrite history.

```bash
git revert abc1234
# Creates a new commit that undoes changes from commit abc1234
```

### Practical Example

```bash
# Starting state - 3 commits
$ git log --oneline
decfe02 (HEAD -> main) Third commit
c9bf72a Second commit
73db7eb First commit

$ cat file.txt 
First commit
Second commit
Third commit

# Revert the latest commit (decfe02)
$ git revert decfe02 
[main 6ededa0] Revert "Third commit"
 1 file changed, 1 deletion(-)

# Result - new revert commit added, original commits preserved
$ git log --oneline
6ededa0 (HEAD -> main) Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit
```

> 💡 Notice: The original commit `decfe02` still exists in history. Git revert creates a **new commit** that undoes the changes.

---

## git reset

**Moves HEAD backward, optionally discarding commits.**

| Flag | Effect |
|------|--------|
| `--soft` | Keep changes staged |
| `--mixed` | Keep changes unstaged (default) |
| `--hard` | Discard all changes |

```bash
git reset --hard HEAD~2
# Removes the last 2 commits and all their changes
```

> ⚠️ Avoid `reset` on shared branches—it rewrites history.

### HEAD~N Notation

`HEAD~N` means "N commits before HEAD":

```
f277ad0 (HEAD)  ← HEAD~0 (current)
5b75696         ← HEAD~1 (1 back)
6ededa0         ← HEAD~2 (2 back)
decfe02         ← HEAD~3 (3 back)
```

### Practical Example: `--soft` reset

```bash
# Starting state
$ git log --oneline
f277ad0 (HEAD -> main) Sixth commit
5b75696 Fifth commit
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

$ cat file.txt 
First commit
Second commit


Fifth commit
Sixth commit

# Reset to HEAD~1 (Fifth commit) with --soft
$ git reset --soft 5b75696

# Commit removed from history, but changes remain STAGED
$ git log --oneline
5b75696 (HEAD -> main) Fifth commit
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

# File content unchanged - changes are staged, ready to re-commit
$ git status file.txt 
Changes to be committed:
  modified:   file.txt

$ cat file.txt 
First commit
Second commit


Fifth commit
Sixth commit

# Re-commit with a new message
$ git commit -m "New commit message"
```

> 💡 `--soft` removes commits but keeps changes staged. File content stays the same.

### Common Use Cases for `--soft`

```bash
# 1. Reword a commit message
git reset --soft HEAD~1
git commit -m "Better message"

# 2. Squash multiple commits into one
git reset --soft HEAD~3
git commit -m "Combined 3 commits into one"

# 3. Add forgotten changes to last commit
git reset --soft HEAD~1
# make additional edits
git add .
git commit -m "Complete feature"
```

### Practical Example: `--mixed` reset

```bash
# Starting state
$ git log --oneline
7d13a7d (HEAD -> main) Seventh commit
d2739b1 reset --soft 5b75696 Fifth commit Head~1
5b75696 Fifth commit
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

# Reset 3 commits back with --mixed
$ git reset --mixed HEAD~3
Unstaged changes after reset:
M       file.txt

# File content unchanged, but changes are UNSTAGED
$ cat file.txt 
First commit
Second commit


Fifth commit
Sixth commit

Seventh commit

$ git status file.txt 
Changes not staged for commit:
        modified:   file.txt

# Must add before committing
$ git add file.txt 
$ git commit -m "Combined multiple commits"

$ git log --oneline
89ef534 (HEAD -> main) Combined multiple commits
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit
```

> 💡 `--mixed` removes commits and keeps changes **unstaged**. You must `git add` before committing.

### Practical Example: `--hard` reset

```bash
# Starting state
$ git log --oneline
89ef534 (HEAD -> main) Combined multiple commits
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

# Reset 1 commit back with --hard
$ git reset --hard HEAD~1
HEAD is now at 6ededa0 Revert "Third commit"

# Commit AND file changes are GONE
$ git log --oneline
6ededa0 (HEAD -> main) Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

$ git status file.txt 
nothing to commit, working tree clean

# File reverted to state at 6ededa0
$ cat file.txt 
First commit
Second commit
```

> ⚠️ `--hard` is destructive! It removes commits AND discards all changes permanently.

### Important Note

> 📌 **Key Insight:** `git reset --soft` and `git reset --mixed` do **NOT** change file content!
> 
> | Flag | Commits | File Content | Changes State |
> |------|---------|--------------|---------------|
> | `--soft` | Removed | Unchanged | Staged |
> | `--mixed` | Removed | Unchanged | Unstaged |
> | `--hard` | Removed | **Reverted** | Discarded |
>
> This is crucial for **rewriting commit messages** or **squashing commits** — your work is preserved, only the history changes.

### How to Squash Commits

**Squashing** = Combining multiple commits into one. Two methods:

#### Method 1: Using `reset --soft`

```bash
# You have 4 commits you want to combine into 1
$ git log --oneline
a1b2c3d (HEAD -> feature) Add tests
e4f5g6h Fix typo  
i7j8k9l Add feature logic
m0n1o2p Start feature

# Reset to before all 4 commits, keep changes staged
$ git reset --soft HEAD~4

# All changes are now staged, create single commit
$ git commit -m "Add complete feature with tests"

# Result: 4 commits → 1 commit
$ git log --oneline
x9y8z7w (HEAD -> feature) Add complete feature with tests
```

#### Method 2: Using `rebase -i` (Interactive)

```bash
# Squash last 4 commits interactively
$ git rebase -i HEAD~4

# Editor opens - change 'pick' to 'squash' (or 's') for commits to combine:
pick m0n1o2p Start feature
squash i7j8k9l Add feature logic
squash e4f5g6h Fix typo
squash a1b2c3d Add tests

# Save and close, then edit the combined commit message
```

> 💡 Use `reset --soft` for quick squashing. Use `rebase -i` when you need more control over which commits to combine.

---

## git rebase

**Replays commits on top of another branch.**  
Creates a linear history by moving your branch's base.

### Two Types of Rebase

| Type | Command | Purpose |
|------|---------|---------|
| Update feature | `git checkout feature; git rebase main` | Get latest main changes into your feature |
| Integrate feature | `git checkout main; git rebase feature` | Bring completed feature into main |

---

### Type 1: Update feature branch with latest main

**When to use:** Main branch has moved ahead while you were working on feature. You want to include those new changes.

```
SITUATION - Main moved ahead while you worked on feature:

main:     commit-1 → commit-2 → commit-5 → commit-6 (teammate added these)
                \
feature:         commit-1 → commit-2 → commit-3 → commit-4 (your work)

Your feature branch is BEHIND main!
```

**Solution:**

```bash
git checkout feature
git rebase main
```

**Result:**

```
AFTER rebase:

main:     commit-1 → commit-2 → commit-5 → commit-6
                                              \
feature:                                       commit-3' → commit-4' (HEAD)

Your commits are "replayed" on top of latest main.
(commit-3' and commit-4' are new commits with different hashes)
```

**Why do this?**

| Reason | Benefit |
|--------|---------|
| Stay current | Your feature includes latest main changes |
| Catch conflicts early | Fix issues before final integration |
| Clean history | Smoother integration later |

---

### Type 2: Integrate completed feature into main

**When to use:** Your feature is complete and you want to bring those commits into main with a linear history.

```
SITUATION - Feature has commits that main doesn't have:

main:     commit-1 → commit-2 (HEAD)
                \
feature:         commit-1 → commit-2 → commit-3 → commit-4 (HEAD)

commit-3 = bugfix for commit-2
commit-4 = new feature
```

**Solution:**

```bash
git checkout main
git rebase feature
```

**Result:**

```
AFTER rebase:

main:     commit-1 → commit-2 → commit-3 → commit-4 (HEAD)
                                              ↑
feature:                                  (same commit)

Main now includes all feature commits in linear history.
```

### Practical Example: Integrate feature into main

```bash
# Check main branch status
$ git checkout main
Switched to branch 'main'

$ git log --oneline
e648890 (HEAD -> main) Eight commit
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

# Check feature branch - has 2 extra commits
$ git checkout feature
Switched to branch 'feature'

$ git log --oneline
5d0d32c (HEAD -> feature) Tenth commit
1cf4612 Nineth commit
e648890 (main) Eight commit
6ededa0 Revert "Third commit"
decfe02 Third commit
c9bf72a Second commit
73db7eb First commit

$ cat file.txt 
First commit
Second commit






Eight commit
Nineth commit
Tenth commit

# Now integrate feature into main using rebase
$ git checkout main
Switched to branch 'main'

$ git rebase feature
Successfully rebased and updated refs/heads/main.

# Result: main now includes all feature commits with linear history
$ git log --oneline --graph
* 5d0d32c (HEAD -> main, feature) Tenth commit
* 1cf4612 Nineth commit
* e648890 Eight commit
* 6ededa0 Revert "Third commit"
* decfe02 Third commit
* c9bf72a Second commit
* 73db7eb First commit
```

> 💡 Notice: Both `main` and `feature` now point to the same commit. The history is linear (no merge commit).

### Rebase vs Merge

| Aspect | Rebase | Merge |
|--------|--------|-------|
| History | Linear | Shows branch structure |
| Merge commit | No | Yes |
| Rewrites history | Yes | No |
| Best for | Clean local history | Shared branches |

---

## git cherry-pick

**Copies a specific commit to your current branch.**  
Useful for grabbing individual fixes from other branches.

```bash
git cherry-pick <commit-hash>
# Applies that commit to current branch as a new commit
```

### Practical Example

```bash
# Feature branch has 2 new commits we want to pick
$ git log --oneline --graph
* 3811932 (HEAD -> feature) Line16 from feature for cherry-pick
* 43eb796 Line15 from feature for cherry-pick
*   6d8068f (main) git merge from feature
|\  
| * 282dd22 Line4 from main
...

# Switch to main branch
$ git checkout main
Switched to branch 'main'

# Cherry-pick ONE specific commit (Line15)
$ git cherry-pick 43eb796
[main 298d3f9] Line15 from feature for cherry-pick
 1 file changed, 1 insertion(+)

# Result: Only that commit's changes are now in main
$ cat file.txt; echo
Line1 from main
...
Line15 from feature for cherry-pick
```

> 💡 The commit is **copied** (new hash), not moved. Original commit stays in feature branch.

---

## git format-patch

**Exports commits as `.patch` files** for sharing via email or other means.

```bash
git format-patch -N
# Creates N patch files for the last N commits
```

### Practical Example

```bash
# On feature branch, create patches for last 2 commits
$ git checkout feature
$ git log --oneline -3
47ad819 (HEAD -> feature) Line17 from feature for format-patch
3811932 Line16 from feature for cherry-pick
43eb796 Line15 from feature for cherry-pick

# Generate patch files
$ git format-patch -2
0001-Line16-from-feature-for-cherry-pick.patch
0002-Line17-from-feature-for-format-patch.patch

# Switch to main and apply patches
$ git checkout main
Switched to branch 'main'

$ git apply 0001-Line16-from-feature-for-cherry-pick.patch
$ git apply 0002-Line17-from-feature-for-format-patch.patch

# Changes applied!
$ cat file.txt; echo
Line1 from main
...
Line15 from feature for cherry-pick
Line16 from feature for cherry-pick
Line17 from feature for format-patch
```

> 💡 `git apply` applies changes but doesn't create a commit. Use `git am` to apply AND commit.

### git apply vs git am

| Command | Applies changes | Creates commit |
|---------|-----------------|----------------|
| `git apply` | ✅ | ❌ |
| `git am` | ✅ | ✅ |

---

## git merge

**Combines two branches together.**  
Creates a merge commit (unless fast-forward is possible).

```bash
git checkout main
git merge feature
# Integrates feature branch into main
```

---

## git bisect

**Binary search to find the commit that introduced a bug.**  
Efficiently halves the search space with each step.

```bash
git bisect start
git bisect bad              # Current commit is broken
git bisect good <commit>    # This commit was working fine
# Git checks out a middle commit; test and mark good/bad
# Repeat until the bad commit is found
git bisect reset            # Return to original state
```

### Practical Example: Finding a Bug

**Scenario:** A Python script should print numbers 1-10, but a bug was introduced somewhere.

#### Commit Progression

| Description | task154.py content | Commit |
|-------------|-------------------|--------|
| Simple loop over static range | `for i in range(1, 11):`<br>`    print(str(i))` | A |
| Change start value to a variable | `start = 1`<br>`for i in range(start, start+10):`<br>`    print(str(i))` | B |
| Change stop value to variable. **Introduces bug** - only 1-9 printed | `start = 1`<br>`stop = 10`<br>`for i in range(start, stop):`<br>`    print(str(i))` | C (bug) |
| Add the suffix `Expert(s)` to the output | `start = 1`<br>`stop = 10`<br>`for i in range(start, stop):`<br>`    print(str(i) + " Expert(s)")` | D |
| Change output string to `DevNet Expert(s)` | `start = 1`<br>`stop = 10`<br>`for i in range(start, stop):`<br>`    print(str(i) + " DevNet Expert(s)")` | E |

```bash
# Commit history
$ git log --oneline
e5f6g7h (HEAD -> main) E - Change output to "DevNet Expert(s)"
d4e5f6g D - Add suffix "Expert(s)"
c3d4e5f C - Change stop value to variable (BUG!)
b2c3d4e B - Change start value to variable
a1b2c3d A - Simple loop over static range (WORKING)
```

The bug: Commit C changed `range(start, start+10)` to `range(start, stop)` where `stop=10`, causing only 1-9 to print.

---

### Method 1: Manual Bisect

```bash
# Start bisect session
$ git bisect start

# Mark current commit (E) as bad
$ git bisect bad

# Mark commit A as good (it was working)
$ git bisect good a1b2c3d
Bisecting: 1 revision left to test after this (roughly 1 step)
[c3d4e5f] C - Change stop value to variable

# Git checks out middle commit - test it manually
$ python3 task154.py
1
2
...
9
# Only prints to 9! Bug is present.

$ git bisect bad
Bisecting: 0 revisions left to test after this (roughly 0 steps)
[b2c3d4e] B - Change start value to variable

# Test again
$ python3 task154.py
1
2
...
10
# Prints to 10! This commit is good.

$ git bisect good
c3d4e5f is the first bad commit
commit c3d4e5f
    C - Change stop value to variable

# Done! Reset to return to original state
$ git bisect reset
```

---

### Method 2: Automated Bisect with Script

Create a verification script `verify-task154.sh`:

```bash
#!/usr/bin/env bash
SCRIPT_OUTPUT=$(python3 task154.py)
if [[ "$SCRIPT_OUTPUT" == *"10"* ]]; then
  exit 0    # Good (found "10" in output)
else
  exit 1    # Bad (no "10" in output)
fi
```

Make it executable and run:

```bash
$ chmod +x verify-task154.sh

# Start bisect
$ git bisect start
$ git bisect bad
$ git bisect good a1b2c3d

# Run automated bisect
$ git bisect run ./verify-task154.sh
running './verify-task154.sh'
Bisecting: 0 revisions left to test after this (roughly 1 step)
...
c3d4e5f is the first bad commit
bisect run success

# Reset when done
$ git bisect reset
```

> 💡 Exit code `0` = good commit, Exit code `1` = bad commit

### Alternative Terms: old/new

Instead of good/bad, you can use old/new:

```bash
git bisect start --term-old=old --term-new=new
git bisect new          # Current has the bug
git bisect old a1b2c3d  # This was before the bug
```

### Bisect Summary

| Command | Purpose |
|---------|---------|
| `git bisect start` | Begin session |
| `git bisect bad` | Mark current commit as broken |
| `git bisect good <commit>` | Mark a known working commit |
| `git bisect run <script>` | Automate with exit codes |
| `git bisect reset` | End session, return to HEAD |

---

## Summary Table

| Command | Purpose | Rewrites History? |
|---------|---------|-------------------|
| `revert` | Undo commit safely | No |
| `reset` | Move HEAD, discard commits | Yes |
| `rebase` | Replay commits on new base | Yes |
| `cherry-pick` | Copy specific commit | No |
| `format-patch` | Export commits as files | No |
| `merge` | Combine branches | No |
| `bisect` | Find buggy commit | No |