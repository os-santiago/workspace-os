# Repository Rules: Workspace OS

Follow ADEV doctrine for all iterations.

## PR Review and Merge Hardening
1. **Approval Justification**: Every PR approval must explicitly document the reasons and validations justifying the approval in the review description/comments.
2. **Apply Available Merges**: If merge is available (all checks have passed and approval is granted), apply/execute the merge immediately.
3. **Clean Up Merged Branches**: Always delete the source branch locally and on remote once the PR is successfully merged to the main branch.
4. **Update Out-of-date Branches**: If a PR is approved but out-of-date/out-of-sync with the base branch, execute the update branch command to trigger the automatic status validations, and continue with the merge and branch deletion once all checks pass.

