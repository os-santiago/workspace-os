# Repository Rules: Workspace OS

Follow ADEV doctrine for all iterations.

## PR Review and Merge Hardening
1. **Approval Justification**: Every PR approval must explicitly document the reasons and validations justifying the approval in the review description/comments.
2. **Apply Available Merges**: If merge is available (all checks have passed and approval is granted), apply/execute the merge immediately.
3. **Clean Up Merged Branches**: Always delete the source branch locally and on remote once the PR is successfully merged to the main branch.
4. **Update Out-of-date Branches**: If a PR is approved but out-of-date/out-of-sync with the base branch, execute the update branch command to trigger the automatic status validations, and continue with the merge and branch deletion once all checks pass.

## Issue Resolution Workflow
1. **Understand Objective**: Always read and treat the issue description as the single source of truth for the implementation.
2. **Dedicated Branch**: Sync with `main` and branch directly from the issue using a dedicated naming convention referring to the issue ID (e.g., `fix/issue-123` or `feat/issue-123`).
3. **Traceability**: In the Pull Request description, explicitly link the issue (e.g., `Closes #123` or `Fixes #123`) to ensure automated closing and traceability.
4. **Verification and Cleanup**: After the PR is successfully merged, verify the issue is closed on GitHub, delete the local and remote branch, and clear any temporary diagnostic scripts or logs.


