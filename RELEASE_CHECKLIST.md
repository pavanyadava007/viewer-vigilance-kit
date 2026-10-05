# Release candidate checklist

Structured like a release review for medical device software. **This is not a regulatory
document** and the project is not a medical device; it shows the shape of the evidence a
release needs and which parts are automated.

## 1. Scope

- [ ] Version number set in `pyproject.toml`, `viewer/__init__.py`, `vigil/__init__.py`
      (the RC gate checks they match each other and the tag).
- [ ] Changes since the last release listed (release notes are generated from conventional
      commits by `scripts/release_notes.py`; review and edit before publishing).
- [ ] Each change linked to a requirement ID in `requirements.yaml`, or marked as no
      functional change (docs, CI, refactor).
- [ ] Intended use unchanged: research and demonstration only, not for diagnosis.

## 2. Verification evidence (automated, `make rc`)

- [ ] `ruff check` and `ruff format --check` clean.
- [ ] Full test suite green: smoke, unit, golden, vigilance monitor (`reports/rc/junit.xml`).
- [ ] Traceability: every requirement has at least one existing test
      (`scripts/traceability.py`, `reports/rc/traceability.md`).
- [ ] Planted-defect study: every defect in `viewer/_defects.py` is caught by the full suite
      (`reports/rc/mutants.json`).
- [ ] RC gate verdict PASS in `reports/rc/rc_report.md`.

## 3. Golden images

- [ ] No golden file changed in this release, **or** every changed golden was reviewed
      visually (old vs new PNG in `tests/golden/`, overlay JSON diff) and the reason is
      written in the release notes.
- [ ] Goldens regenerated only with `scripts/make_goldens.py` and never with a defect switch on
      (the script refuses).

## 4. Manual checks on the release candidate

- [ ] Render the bundled CT, MR, axial and sagittal phantom with `dicomview`; orientation
      letters, W/L text and a known measurement (phantom: 52 rows x 0.8 mm = 41.6 mm) correct.
- [ ] Contrast and brightness change the image in the expected direction.
- [ ] Series order: the phantom bar length grows with slice index.

## 5. Known anomalies

List every open defect with its risk assessment and workaround. For 0.1.0:

| ID | Description | Impact | Decision |
|---|---|---|---|
| KA-1 | Zoom uses nearest-neighbour sampling only | Blocky images at high zoom | Accepted for a demo core |
| KA-2 | BfArM relevance from titles is weak (see README) | Missed notices if the Produktgruppe filter is removed | Group filter kept on |
| KA-3 | openFDA MAUDE data lags by weeks | Digest is late for MAUDE | Window of 90 days plus state file |

## 6. Vigilance input for this release

- [ ] Latest weekly digest reviewed (`vigilance-weekly` workflow artifact or issue).
- [ ] Any incident in a category the release touches (display, orientation, measurement,
      wrong patient, data loss, interoperability) checked against the change list.

## 7. Release

- [ ] Tag `vX.Y.Z` pushed; `release` workflow green; GitHub Release has wheel, sdist, RC
      report, trace matrix, defect study and digest sample attached.
- [ ] Release notes reviewed after publication.
