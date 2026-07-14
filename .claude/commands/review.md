---
description: Review the current branch diff for issues before merging
---

## Files Changed
!`git diff --name-only main...HEAD`

## Full Diff
!`git diff main...HEAD`

Review every changed file for:
1. Missing input validation
2. Security or data exposure risks
3. Missing or incomplete test coverage
4. Performance issues
5. Error handling gaps

Give specific, actionable feedback per file. Flag blockers vs nice-to-haves.
