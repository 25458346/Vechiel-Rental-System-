# Evidence guide

Student: Surafel Biruk Abay. Registration: std3168. Tutor: Ravushnar. Submission: 28 September 2026.

The Word reports explain Tasks 3 and 4. This folder preserves genuine Jenkins outputs and screenshots. The submitted application source is the corrected revision tested in build 3.

## Build sequence

| Build | Revision | Result | Evidence |
| --- | --- | --- | --- |
| 1 | 7815da3 | SUCCESS | 37 tests passed; live and security gates passed; initial ZIP archived. |
| 2 | 057a8d4 | FAILURE | Deliberate doubled-count fault; 34 tests passed and 3 failed; live scan and release skipped. |
| 3 | afbe917 | SUCCESS | Corrected source; 37 tests passed; all required security gates passed; verified source archived. |

Builds 2 and 3 were triggered by SCM changes. The archived console files and build metadata record their causes and revisions. The initial release manifest had a null commit field; build 3 corrects that traceability issue. This limitation is retained, not concealed.

Each build directory contains build.json, console.txt and original archived reports. Successful builds also contain the delivered source ZIP. reports/release.json holds its SHA-256 checksum and database checksum. Reports at the project root describe build 3, except the separate source provenance and initial full-data import statistics. Re-running checks replaces those local reports.

## Screenshot annotations

1. screenshots/build-2-failed-tests.png shows Jenkins listing the three failing count tests out of 37. Their fixed numeric expectations detected the deliberately doubled output.
2. screenshots/build-2-blocked-stages.png shows the failed functional stage and skipped live and delivery stages. The complete console confirms the skipped stages and final FAILURE.
3. screenshots/build-3-success-stages.png shows all stages succeeding after correction, including delivery and artifact archival.
4. screenshots/build-3-passed-tests.png shows 37 tests and no failures in Jenkins.
5. screenshots/build-3-artifacts.png shows the successful build and its retained reports and verified source artifact.

These are original UI captures. Full report data and complete logs accompany them because a screenshot alone cannot prove every security check.

## Assessment mapping

| Criterion | Evidence |
| --- | --- |
| 3.1 | Task 3 sections 3 1 to 3 3 and 3 5 to 3 6; complete 3,475,226-row source provenance, importer, aggregate database and usable analysis app. |
| 3.2 | Task 3 section 3 4; separated modules, reader protocol, injected service, validation and substitution tests. |
| 3.3 | Task 4 sections 4 1 to 4 4; specified expected outcomes, executable pytest tests, SCA, SAST, live checks and DAST reports. |
| 3.4 | Task 4 section 4 6; benefits, costs and limits of automation, illustrated by staged pipeline results. |
| 3M1 | Task 4 section 4 5; real Jenkins success, controlled failure, blocked delivery and corrected success. |

Tasks 3 and 4 do not have a separate distinction criterion in the supplied brief. Task 2 has 2D1 and Task 1 has 1D1. These deliverables do not certify that every criterion across the unit is met; the assessor determines the grade. Task 2 still needs its written submission and separate review.

## Manual demonstration

Open http://127.0.0.1:18090/job/Transport-Demand/ while the local Jenkins instance is running. Its login is stored separately on the student's computer, outside this submission.

Open build 3, select Tests and show the 37 passing cases. Open Pipeline Overview to explain the stage order. Return to build 3 and open the archived release.json, security reports and verified ZIP. Open build 2 and show the three failing tests and skipped release stage. Explain that the fault was intentional and is corrected in the submitted source.

To perform another run, use Build Now on the job, wait for completion, and inspect its own results. Do not assume a new run succeeds because build 3 passed. The README in the project folder gives local application and verification commands for a machine without this Jenkins setup.

The app uses a local descriptive transport dataset. The demonstration does not establish production deployment, rollback, concurrent capacity, forecast accuracy or absence of all vulnerabilities.
