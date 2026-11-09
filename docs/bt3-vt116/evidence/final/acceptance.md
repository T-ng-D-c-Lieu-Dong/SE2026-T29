# VT-116 final acceptance

**Local artifacts: READY FOR STUDENT REVIEW. GitHub deliverable: BLOCKED.**
This is not READY FOR SUBMISSION and does not sign the student's reflection/academic commitment.

Backend/harness tested commit: `c3421e27c5885857dea0b14f6358954b5a80ddb1`.
Final clean-revision regression: `7f5f56f96cd53fb2a2939d5ab8aa7571ea0fdb4f`, 117 pass / 0 fail / 0 skip, 3.46 s, one dependency deprecation warning.
Later changes package documents/PDF only. Obtain final artifact commit with `git log -1 --format=%H -- docs/bt3-vt116`; the actual final HEAD is also reported at handoff.

Evidence paths below are relative to `docs/bt3-vt116/`.

| Check | Status | Evidence and limits |
|---|---|---|
| Missing identity / cross-user / equal-name isolation | PASS | `evidence/final/09-full-pytest.log`, `18-final-regression.log`; API guards; owner sourced only from asserted caller |
| Historical ownership / migration | PASS | `evidence/final/08-migration.log`, legacy/name security tests; migration0003 disables every existing row; verified administrative reassignment remains a separate process |
| Authentication / anti-spoofing | PARTIAL | Characterization tests reproduce forged headers; no trusted ingress/IdP or network E2E implemented. Header presence is not authentication |
| Full regression | PASS | `evidence/final/18-final-regression.log`: 117 PASS, 0 FAIL, 0 SKIP; one Starlette deprecation warning |
| Selected state transitions | PASS | the PDF test matrix and Appendix A; TC-11, cancelled lifecycle and deleted-cancel now executed; 33 VT-116 items pass |
| One deliberate mutation | PASS | `evidence/final/13-mutation.log`; temporary SHA1b707ea: 12 fail / 21 pass, killed; not in submitted branch; no generic mutation percentage claimed |
| Statement / branch coverage | PASS | `evidence/final/10-coverage-sysmon.log`, `11-coverage-report.log`, `coverage.json`: 808/859 statements, 166/200 branches. Former exit139 cause NOT VERIFIED |
| Risk coverage | PARTIAL | Five ACs and exact executable mappings in PDF Appendix A/B; AC-04 limited by missing real authentication; DB race rollback interleavings not fully forced |
| Time / shared-state / order flaky review | PASS | `evidence/final/14-flaky-review.log`: 33 pass in each of 3 timezone/order runs; bounded observation, not proof of flake freedom |
| Performance / JSON-text agreement | PASS | Paired `evidence/final/performance-20261109T063500Z-038fb4c8.json` and `.log`; `15-performance-consistency.log`; 200/200 lifecycles, 600 requests, peak40, p95 420.11ms. ASGI in-process; not production capacity |
| README reproducibility | PASS | Actual isolated Docker, migration, pytest, coverage, flaky and load commands executed; correct compose file/credentials; scripts guard test DB. No shared DB touched |
| Traceability / AI log | PASS | PDF Appendix A/B and PDF appendices: exact test names/files/tested SHA/results; historical uncertainties and rejected assumptions declared |
| PDF layout / main page limit | PASS | `evidence/final/16-xelatex-build.log`, `19-pdf-qa.txt`; no overfull hbox/vbox; all pages rendered/inspected; 6 main pages, appendices separated. One forced page break before appendix; long tables flow naturally |
| Reflection | PARTIAL | 301 whitespace-separated words; AI-assisted draft for student's own editing/confirmation; no personal experience or signature attested by AI |
| Cleanup | PASS | Redundant intermediate diagnostics, duplicated load capture, stale unpaired performance files and duplicate trace JSON removed. Historical RED/GREEN/mutation and original audit/plan retained under `evidence/planning/`; historical logs under `evidence/historical/`; removed committed diagnostics remain in Git history |
| Git branch / remote | PASS | Branch `bt3/23001827-vt116-soft-delete-restore`; remote `https://github.com/CuongMotNang/SE2026-T29.git`; no merge/history rewrite |
| GitHub branch URL / push | BLOCKED | `evidence/final/17-github-readonly.log` returned no matching branch. Automatic approval review rejected `git push -u origin bt3/23001827-vt116-soft-delete-restore`: remote ownership/trust and explicit authorization for this exact egress were not recognized. No retry/workaround, fabricated URL or claim of successful push |
| Final Git status | PASS | All intended changes committed; final handoff verifies `git status --short` and reports actual HEAD. engineering evidence commit can be resolved using command above |

## Remaining action

Automatic approval review blocked the push (exact reason above). In addition, read-only inspection found that historical commit `d864f1c` added PDF/LaTeX and `84bc880` removed them from the tree. They still exist in branch history. No push has occurred in this correction.

The current user instruction excludes both PDF and LaTeX from GitHub. An ordinary push of this branch would also upload their historical objects, despite a clean current tree. A reviewed history/export decision is required before any future push. Do not bypass the approval rejection, rewrite RED/GREEN history, or assume removing files from the current tree removes them from history. The present branch and all original RED/GREEN commits are preserved.

## PDF rebuild

From the workspace parent containing the root `.tex`:

```bash
docker run --rm --user 1000:1000 \
  -v /home/anhzxje/Documents/Projects/SE:/work -w /work \
  --entrypoint xelatex blang/latex:ubuntu \
  -interaction=nonstopmode -halt-on-error BT3_23001827_VT-116.tex
```

Run twice. Both `.tex` and `.pdf` stay in the workspace parent, outside the repository, per the student's explicit instruction. No PDF/LaTeX is staged or pushed in this correction. Historical commit d864f1c already contains old PDF/LaTeX; a future ordinary push would also send those historical objects. Therefore no ordinary push should be attempted under the current no-document-upload requirement until the branch history/export strategy is explicitly resolved. PNG previews/build auxiliaries stay outside this document folder; raw XeLaTeX build log is retained as evidence.
