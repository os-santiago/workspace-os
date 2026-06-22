# ADEV Enforcement in WOS

**Status**: Active  
**Version**: 1.0  
**Last Updated**: 2026-06-21  
**Related Issue**: #86

---

## Purpose

WOS enforces ADEV (AI-Assisted Development) workflow rules automatically to ensure:
- Code quality through mandatory review
- Atomic, revertible commits
- Clear audit trail
- SOC2/ISO compliance readiness

---

## ADEV Rules Enforced

### Rule #1: Atomic PRs
**Source**: `D:/kb/adev/ADEV.md` line 14

> **"Default mode: each iteration must ship from a dedicated branch and a single atomic PR with a clear objective."**

**WOS Enforcement**:
- ✅ Cycle prompts ALWAYS include PR workflow instructions (regardless of `WOS_ENABLE_ISSUE_ASSIGNMENT`)
- ✅ Instructions appear in EVERY cycle, not conditionally
- ✅ Agents receive numbered step-by-step PR creation guide

---

### Rule #3: Atomic Commits
**Source**: `D:/kb/adev/ADEV.md` line 17

> **"Commits must be atomic and use Conventional Commits."**

**WOS Enforcement**:
- ✅ Prompts specify Conventional Commits format explicitly
- ✅ Prohibitions against batch commits stated clearly
- ✅ "ONE issue = ONE commit = ONE PR" rule emphasized

---

### Rule #4: No Mixing
**Source**: `D:/kb/adev/ADEV.md` line 18

> **"Do not mix refactor, feature, visual changes, infrastructure, doctrine updates, and release mechanics in the same PR unless batch delivery is explicitly requested."**

**WOS Enforcement**:
- ✅ Explicit prohibition in prompts
- ✅ Warning against mixing unrelated changes
- ✅ Single responsibility principle emphasized

---

### Rule #48: Complete Lifecycle
**Source**: `D:/kb/adev/ADEV.md` line 81

> **"When resolving a scoped issue, follow a unified lifecycle: read the issue to lock implementation scope, sync with main, branch using a dedicated feature branch containing the issue ID (e.g. fix/issue-123), implement local validations, link the issue in the PR description (e.g. Closes #123) for automatic closure, and perform post-merge cleanup by deleting the source branch locally and on remote."**

**WOS Enforcement**:
- ✅ Complete 11-step workflow in every prompt
- ✅ Branch naming convention specified
- ✅ Issue linking format specified
- ✅ Cleanup instructions included

---

## Enforced Workflow

Every WOS cycle includes these instructions:

```
================================================================================
CRITICAL: ADEV-COMPLIANT WORKFLOW (NON-NEGOTIABLE)
================================================================================

ADEV Rule #1: Each iteration must ship from a dedicated branch and a single atomic PR.
ADEV Rule #3: Commits must be atomic and use Conventional Commits.
ADEV Rule #48: One issue → One branch → One PR → Merge → Cleanup

WORKFLOW ENFORCEMENT:
1. NEVER commit directly to main branch
2. ONE issue = ONE dedicated branch = ONE atomic PR
3. Branch naming: fix/issue-NNN or feat/issue-NNN or feat/descriptive-name
4. Create branch: git checkout -b fix/issue-NNN
5. Implement ONLY the scoped issue (do NOT batch multiple issues)
6. Commit atomically with Conventional Commits format:
   git commit -m "fix: <description> (Closes #NNN)"
7. Push branch: git push -u origin fix/issue-NNN
8. Create Pull Request:
   gh pr create --title "fix: <description>" \
     --body "Closes #NNN\n\n<detailed description>" \
     --fill
9. Link issue in PR body with 'Closes #NNN' for automatic closure
10. DO NOT merge yourself - wait for CI checks and review
11. After merge: delete local and remote branch

PROHIBITED (ADEV violations):
- ❌ Batch commits with multiple issues (violates atomic commit rule)
- ❌ Direct commits to main (violates PR workflow)
- ❌ Mixing unrelated changes in one PR (violates single responsibility)
- ❌ Commits without creating PR (violates code review requirement)
```

---

## Implementation

### File: `src/workspace_os/cycle.py`
**Function**: `_build_cycle_work_prompt()`  
**Lines**: ~559-620

**Before Issue #86 Fix**:
```python
if gh_issues_hint:  # BUG: Conditional
    base_lines.append("CRITICAL INSTRUCTIONS FOR ISSUES:")
    # ... PR instructions ONLY if gh_issues_hint is populated
```

**After Issue #86 Fix**:
```python
# ALWAYS enforce ADEV-compliant PR workflow
base_lines.append("CRITICAL: ADEV-COMPLIANT WORKFLOW (NON-NEGOTIABLE)")
# ... PR instructions ALWAYS present, regardless of issue assignment mode
```

---

## Exceptions

### Batch Delivery (Explicit Approval Required)

**When allowed**:
- Objective explicitly mentions "batch delivery"
- Multiple related issues approved for single PR
- Still requires atomic checkpoints per issue

**Requirements**:
- Each issue still needs atomic commit
- Rollback plan documented
- Validation per stage
- Explicit approval from human

**Example objective**:
```
"Batch delivery: Resolve issues #101, #102, #103 in single PR.
Each issue gets atomic checkpoint. Rollback plan: revert to checkpoint N."
```

---

## Configuration

### `WOS_ENABLE_ISSUE_ASSIGNMENT`

**Default**: `true`

**When `true`**:
- WOS fetches GitHub issues
- Assigns issues to agents
- Adds issue-specific context to prompts
- PR workflow instructions included

**When `false`**:
- WOS skips issue assignment
- Agents discover issues themselves
- ⚠️ **BEFORE Issue #86**: PR instructions were SKIPPED (BUG)
- ✅ **AFTER Issue #86**: PR instructions ALWAYS included (FIXED)

---

## Testing

### File: `tests/test_adev_enforcement.py`

**Test Cases**:

1. **`test_pr_workflow_always_enforced_with_assignment_disabled()`**
   - Regression test for Issue #86
   - Verifies PR instructions present when `WOS_ENABLE_ISSUE_ASSIGNMENT=false`
   - Asserts ADEV rules are stated
   - Asserts prohibitions are clear

2. **`test_pr_workflow_enforced_with_assignment_enabled()`**
   - Verifies original mode still works
   - Checks issue-specific context added

3. **`test_adev_prohibitions_clearly_stated()`**
   - Verifies prohibitions section exists
   - Checks batch commits warned against

4. **`test_regression_issue_86_batch_commit_prevented()`**
   - Specific test for homedir cycle bug
   - Simulates exact conditions that caused violation
   - Verifies fix prevents recurrence

**Run tests**:
```bash
pytest tests/test_adev_enforcement.py -v
```

---

## Evidence of Bug (Before Fix)

### Homedir Issues Resolution Cycle
**Date**: 2026-06-21  
**Config**: `WOS_ENABLE_ISSUE_ASSIGNMENT=false`  
**Result**: ADEV violations

**Commit 652bd272**:
```
fix: P1/P2 issues batch - test isolation, secret redaction, authz tests

P1 - Issue #895: Fix i18n locale test isolation
P2 - Issue #887: Enhance secret redaction  
P2 - Issue #875: Document structured logging standard
P2 - Issue #886: Systematic authorization bypass tests
```

**Violations**:
- ❌ 4 issues in 1 commit (non-atomic)
- ❌ No PR created (direct commit)
- ❌ Mixed changes (test + feature + docs)
- ❌ Not independently revertible

**See**: `D:/git/HOMEDIR_ISSUES_RESOLUTION_REPORT.md`

---

## Compliance Impact

### Enterprise Requirements Met

**After Issue #86 Fix**:

✅ **SOC2 Compliance**:
- Code review enforced (all changes via PR)
- Audit trail complete (PR history)
- Approval workflow present

✅ **ISO 27001**:
- Change management process enforced
- Traceability maintained
- Quality gates present

✅ **ADEV Compliance**:
- Atomic commits enforced
- PR workflow mandatory
- Single responsibility maintained

---

## Related Documentation

- **ADEV Source**: `D:/kb/adev/ADEV.md`
- **Bug Report**: `D:/git/WOS_CRITICAL_BUG_PR_WORKFLOW.md`
- **Fix Plan**: `D:/git/workspace-os/FIX_ISSUE_86_PR_WORKFLOW_ENFORCEMENT.md`
- **Issue**: https://github.com/scanalesespinoza/workspace-os/issues/86

---

## Changelog

### v1.0 (2026-06-21)
- Initial policy document
- Implemented Issue #86 fix
- Added comprehensive tests
- Documented enforcement mechanism

---

**Policy Owner**: WOS Core Team  
**Review Cycle**: Quarterly  
**Next Review**: 2026-09-21
