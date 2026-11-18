# Bookbinder 4 — Prepress, Restoration, and Casebinding Roadmap

Status: APPROVED FOR PLANNING; NOT IMPLEMENTED. Updated 2026-11-18.
Canonical reference for future LLM agents and maintainers. Repository: AllenConnor00/bookbinder-4.0.
Source of intent: user wants to print illustrated books as folded signatures on US Letter (8.5 × 11 in) sheets, then sew/bind into a formatted casebound hardcover. This document records the design plan, not verified implementation claims.

## 0. Operating rules for agents
- Read this document before working on preprocessing, PDF quality, typography, illustrations, signatures, or casebinding. Also read README.md and inspect current source/tests before editing.
- Do not assume this roadmap describes already implemented features. Distinguish verified current code from proposals. Preserve the existing signature/imposition behavior.
- Local-first, free/open-source where practical; no paid services, mandatory cloud inference, or GitHub Actions validation. Use local automated tests and physical print proofing.
- Never overwrite input PDFs. Every transformation is optional, versioned, previewable, reversible, and traceable, with per-page provenance and a machine-readable QA report.
- Do not silently invent text, accents, artwork, or layout. OCR/AI restoration is an aid, not an authority. Flag uncertain changes for review.
- Do not bundle copyrighted books, scans, or artwork in the repository; use synthetic, public-domain, or explicitly licensed fixtures.
- Preserve user attention: batch low-risk operations, surface only actionable exceptions, and require review for destructive or ambiguous changes.

## 1. Existing foundation — verify against code
README describes React/Vite UI, FastAPI backend, PyMuPDF PDF processing, health checks, previews, configurable folio patterns (e.g. 4,4,3), crop/sewing marks, creep/gutter, print-safe margins, page-box selection, raster flattening vs vector preservation, and signature/PDF export. requirements.txt lists FastAPI, PyMuPDF 1.24.14, Pillow 11.1.0, pytest; frontend/package.json lists React 19, PDF.js, TypeScript, Vite. These are repository-documentation claims, not independently executed behavior.

## 2. User's immediate target and geometry
- US Letter sheet, landscape folded once, produces nominal 5.5 × 8.5 in leaves before any trimming. Actual trimmed page must be smaller if trimming is planned; account for printer nonprintable area, fold, creep, and trim.
- User is evaluating an illustrated, digitally formatted 461-page Silmarillion PDF vs a scanned Ballantine paperback; illustrated edition is preferred aesthetically but needs source-specific validation. Do not embed either source in repo.
- Source-specific suspected defects: oversized digital page canvas, rasterized body text with separate selectable/OCR layer, blue hyperlink-styled headings, electronic navigation/divider pages, artwork needing careful resampling, variable blank pages. Treat these as hypotheses to verify with the actual source.
- 1484 × 1920 px illustrated pages yield about 226 pixels/in at 8.5 in page height if image fills height; this is not equivalent to 300-PPI typeset text. Estimate effective DPI after final placement, not from PDF metadata.
- Binding thickness and case geometry require actual stock caliper, page count, fold/signature structure, adhesives, boards, covering material, and allowances; no universal fixed spine formula.

## 3. Pipeline and interfaces
Original PDF (immutable) -> page inventory/preflight -> optional source cleanup -> content-preserving normalization -> optional typography/art restoration -> interior layout and mirrored margins -> validated normalized PDF -> existing imposition engine -> imposed signatures -> print proof and physical-binding package.
Implement as an independent prepress subsystem with typed, versioned settings and intermediate artifacts, not scattered ad hoc edits inside imposition.
Suggested modules (names illustrative, determine actual paths after code audit):
- page_inventory: page boxes, dimensions, orientation, embedded fonts, images and effective DPI, raster/vector classification, text layer, annotations/links, color spaces, transparency, content bounding boxes, blanks, clipping.
- normalization: safe fit/scale/crop, source-to-target transforms, content margins, facing-page parity, blank classification.
- digital_cleanup: remove hyperlink annotations independently from appearance; identify visible link colors/underlines only when distinguishable; flag questionable navigation/section pages, never delete automatically.
- enhancement: painting/photo vs line art/maps vs text; safe contrast/denoise/sharpen; optional upscale with QA; preserve color management; no hallucinated detail.
- typography_reconstruction: optional OCR/text-layer extraction, reading order, glyph and diacritic audit, paragraph matching, font embedding, typesetting, page reflow with illustration anchors, source-to-output text diff, human approval gates.
- print_qa: target-DPI checks, safe zones, clipping, missing pages, duplex/sheet order, folio parity, color handling, signatures, proof previews.
- casebinding: book-block thickness, signature count, endpapers, sewing templates, grain direction prompts, board dimensions, square/overhang, hinge gaps, spine lining and covering wrap allowances; all configurable with units and assumptions.
- job_manifest: source hash, transformations, parameters, app versions, warnings, QA results, outputs.

## 4. Prioritized milestones and acceptance criteria
### A — Reliable print-ready interiors (first)
1. Audit current repo and establish baseline regression tests, with no source mutation.
2. Per-page preflight with effective DPI at actual imposed size, raster/vector and text-layer detection, page boxes, blank-page classification, color/link/annotation inventory.
3. Normalize page geometry to chosen trim and printable area, with facing-page mirrored margins, scale-only default, explicit crop warnings, and optional intentional blanks.
4. Remove PDF link annotations safely; visual hyperlink styling and digital-only pages require separate preview/approval.
5. Before/after previews, bulk exception review, reproducible normalized PDF and QA JSON.
Acceptance: no unexpected page loss/reorder; correct final physical dimensions; preserved vector content where available; all risky transformations surfaced; local regression tests and manual duplex proof pass.

### B — Premium content restoration (second)
1. Distinguish text, map/line art, and color paintings and apply category-specific pipelines.
2. Conservative image processing with side-by-side pixel/print-size preview, measured effective DPI and provenance.
3. Optional typography reconstruction from verified text/OCR; preserve special names/diacritics, headings, footnotes, page numbering and illustration anchors.
4. Compare reconstructed text against source with confidence thresholds; block export when unresolved substantive changes exist.
Acceptance: measurable improvements without invented glyphs/art, no silently changed wording, repeatable deterministic fallback.

### C — Hardcover production package (third)
1. Project wizard: Letter duplex folded signatures, paper weight/caliper, trim, grain direction, binding method, printer nonprintable margins.
2. Reuse existing imposition/creep/gutter logic and validate with folding mockups; do not duplicate page ordering code.
3. Estimate book-block thickness, calculate endpapers and case/board/spine/hinge/wrap layout with editable tolerances and clear assumptions.
4. Export signatures, optional sewing-hole guide, printer calibration sheet, case-cover template, cutting/assembly guide, job manifest and QA report.
Acceptance: physical proof can be folded in correct order; no lost gutter text; cover template matches measured physical block; repeatable export.

## 5. UX direction
Single Book Studio flow: Source -> Preflight -> Prepress -> Interior Layout -> Signatures -> Case & Export.
Use a dual-page original/prepared preview with synchronized zoom and print-size mode, a warning queue grouped by severity and page, safe presets and advanced controls. Show per-page before/after and a final imposed sheet view. Allow one-click revert per operation. Never imply a green QA badge means a physical printer was tested.

## 6. Detailed risk controls
- Page numbering vs PDF indices: distinguish logical printed page number, PDF index, signature blank, and deliberate section blank.
- Page parity: insertions/deletions shift recto/verso and all subsequent signature order; recalculate after changes.
- Hyperlink removal: deleting an annotation does not remove blue/underlined pixels baked into raster; changing those pixels can destroy legitimate artwork/text. Require high-confidence detection or manual correction.
- OCR: text selection does not prove vector text. Determine glyph drawing commands and text extraction separately.
- Image resolution: effective DPI = source pixels / final placed inches, per axis; never trust canvas metadata alone. Beware sharpening halos and fine-map labels.
- Color: explicitly support RGB-to-printer workflows and proofing; avoid claiming accurate CMYK without profiles/actual printer tests.
- Scale: preserve aspect ratio unless explicitly approved; report clipping and forced reflow.
- Safety: PDF inputs may be malformed; bound CPU/memory and processing time, sandbox paths, limit decompression, preserve source, report failures.
- Case: paper grain and fold direction, board thickness, cloth/paper wrap, hinge allowance, square, and endpaper structure matter; estimates must be adjustable.
- IP: only transform user-provided authorized material, do not redistribute copyrighted fixtures.

## 7. Suggested tests
Unit: boxes and transforms, mirrored margins/parity, effective DPI, blank classification, annotation removal, page-count invariants, color/image classifications, spine math.
Integration: mixed page sizes/orientations, full-raster books, vector text, mixed vector/raster, maps across spreads, intentional blanks, bookmarks/links, damaged PDFs, non-ASCII glyphs, large files.
Golden PDFs: synthetic/rights-cleared input -> normalized -> imposed -> page-order assertions and pixel comparisons with tolerances.
Physical proof: duplex 100% actual size, fold and stack, inspect trim/gutter/sewing placement, compare print to digital.
Run tests locally; no GitHub Actions requirement.

## 8. Implementation examination checklist (not completed by this document)
- Locate actual backend entrypoints, route handlers, imposition engine, render/flatten functions, health-check implementation, PDF metadata/page-box handling, outputs/job lifecycle.
- Locate frontend app state, upload controls, preview renderer, settings schema, error/warning presentation, export.
- Read existing tests and fixtures, run baseline locally if environment permits.
- Produce a file-by-file change map, data contracts, migration strategy, risk register, acceptance tests, and estimated milestones before implementation.
- Avoid modifying code until examination and review are complete.

## 9. Decisions still requiring user input only when necessary
- Intended final trim (default untrimmed nominal 5.5 × 8.5), whether edges will be trimmed, paper stock/caliper and grain, printer duplex/printable area, sewn vs glued or hybrid construction, cover material, board thickness, and desired restoration aggressiveness. Defaults should be offered; do not block preflight on these choices.

## 10. Handoff prompt for future agents
Read this roadmap, README, actual implementation and tests. First report verified vs documented functionality and exact files to modify. Build Milestone A before B/C, preserving original PDFs and imposition invariants. Use locally verifiable tests, before/after quality evidence, and physical print proof criteria. Do not claim a feature exists merely because this plan describes it. Respect no paid services, no mandatory GitHub Actions, and minimal user interruptions.

## 11. Verified source-code audit (2026-11-18; static review, not executed)
Inspected actual files on default branch: `backend/bookbinder4/main.py`, `backend/bookbinder4/models.py`, `backend/bookbinder4/pdf_engine.py`, `backend/bookbinder4/binding.py`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/package.json`, `requirements.txt`, `scripts/dev.py`, `tests/test_binding.py`.

### Confirmed structure and interfaces
- `main.py` routes: `POST /api/pdf/inspect` (upload), `POST /api/imposition/plan`, `POST /api/imposition/export`, `POST /api/preview/render`, `POST /api/preview/contact-sheet`, `POST /api/tools/calibration`, and `GET /api/preview/{job_id}/{sheet_index}`. Uses FastAPI and `pdf_engine` functions.
- `models.py`: `ImpositionSettings`, `PdfPageInfo`, `PdfInspectResult`, `PreflightItem`, `ImpositionPlan`, `ExportResult`, and preview/calibration requests. Current `PdfInspectResult.pages` is an array of page geometry, but backend returns only first 20 entries.
- `pdf_engine.py` (~431 lines): `save_upload`, `path_for_job`, `inspect_pdf`, `plan_for_job`, `export_job`, `render_preview`, `_write_pdf`, `_place_vector`, `_place_raster`, `validate_export_outputs`. Upload is saved under `backend/data/uploads` with hash-derived job ID; exports under `outputs/<job-id>`.
- `inspect_pdf` iterates all pages for page size, rotation, boxes, presence of annotations and embedded images, plus document forms/layers/modern-feature checks. It does NOT yet report per-page effective image DPI at final placement, vector-vs-raster text, visible link styling, text confidence, actual content bounds, source blank classification, or print clipping. `page.first_annot` does not comprehensively inventory links; links require separate inspection.
- `_write_pdf` chooses raster for both `fidelity='raster'` and `fidelity='hybrid'`; vector only for `fidelity='vector'`. Current 'hybrid' export warning says 'vector-first' despite raster placement; treat as a code/documentation inconsistency to resolve with tests before relying on hybrid.
- `_place_raster` renders at `settings.raster_dpi/72` via PyMuPDF then inserts a raster; output 300 DPI is rendering resolution, not a guarantee of source detail. `_fit_rect` implements fit/fill/stretch; validate crop/clipping and aspect ratio in tests.
- `export_job` deletes the existing output directory for the job with `shutil.rmtree` before regeneration. Prepress intermediates and previous export versions MUST be stored separately and not deleted inadvertently.
- `validate_export_outputs` currently checks output PDFs for nonzero page count; no page-level print QA.
- `binding.py`: `parse_custom_folios`, `page_sequence`, `standard_folios`, `folios_for_settings`, `split_signatures`, `booklet_slots`, `perfect_bound_slots`, `slot_rects`, `build_plan`. Imposition order and creep logic are already present and should be treated as a protected dependency.
- `tests/test_binding.py` has tests for folio parsing, one/two-folio order, blank padding, signature repetition, perfect-bound order, creep and margin bounds. Tests were read, NOT run.
- `frontend/src/App.tsx` is a single React screen with upload, binding settings, debounced plan/preview fetch, warnings, sheet preview, export, contact sheet and calibration. Default settings: Letter 612×792 pt, custom 4 folios, raster fidelity, 300 DPI, short-edge duplex. The UI currently has no prepress stage or page-by-page source preview.

### Priority defects / design constraints discovered
1. Existing inspection truncates geometry details to first 20 pages; introduce paginated or separate full-page inventory without bloating upload responses.
2. Distinguish link annotations from visual link-colored raster pixels. Removing links alone will not remove blue headings baked into source images.
3. Resolve 'hybrid' semantics and validate source-vs-output rendering rather than claiming it preserves vector text.
4. Protect previous outputs; separate immutable source, analysis cache, normalized intermediates, and versioned export paths.
5. Add strict job-ID/path validation before introducing new file-access endpoints; bound upload size and PDF inspection workload.
6. Introduce proper exception handling, abort/retry and stale-response protection in the React fetch flow as preflight becomes asynchronous.
7. Custom folio parsing currently extracts positive integers from arbitrary text; stricter validation may be desirable but is separate from initial preflight work.
8. Do not assume a successful export is print-safe; add explicit validation gates and clear QA statuses.

## 12. First development branch: read-only advanced preflight
Suggested branch name: `feat/read-only-pdf-preflight`.
Scope strictly to inspection and reporting; no PDF transformations, export behavior changes, AI processing, or signature algorithm changes.

### Proposed incremental file map
- New `backend/bookbinder4/preflight.py`: isolated inventory routines and pure effective-DPI/geometry calculations; per-page structured findings, summary aggregation; careful PyMuPDF API version compatibility.
- `backend/bookbinder4/models.py`: typed `PagePreflight`, `ImagePlacementInfo`, `PreflightSummary`, `PreflightReport` schemas with schema version and per-page index.
- `backend/bookbinder4/main.py`: new read-only `GET /api/pdf/preflight/{job_id}` with optional page range and target placement geometry; return 404/422 for invalid jobs/parameters; no destructive operations.
- `backend/bookbinder4/pdf_engine.py`: minimal adapter to reuse immutable source job lookup; avoid mixing new analysis into imposition.
- `frontend/src/App.tsx`: initially a small advanced preflight summary and page-specific warning navigator; later refactor into separate components after API stabilizes.
- `tests/test_preflight.py`: synthetic PDFs covering vector text, raster text, mixed images, annotations vs links, intentionally blank pages, mixed boxes, rotated pages, effective DPI, malformed input and invalid IDs.

### Minimum per-page report contract
PDF page index (0-based internal, 1-based display), geometry/rotation/boxes, content/text/images/links/annotations counts, presence of raster/vector text (with explicit 'unknown' when detection is inconclusive), image placements and effective DPI at specified final placement, blank classification with confidence, warnings with severity and evidence. Do not equate a selectable OCR layer with actual vector glyph rendering.

### Acceptance gate for first PR
- Read-only behavior demonstrably leaves source hash unchanged.
- Reports cover ALL pages (pagination supported), including beyond page 20.
- Correct image effective DPI after scaling to target 5.5 × 8.5 in pages; explicit uncertainty for image transforms/rotation.
- Source image and PDF glyph/text-layer classifications are accurately distinguished on synthetic fixtures.
- Links are inventoried separately from annotations and appearance.
- Malformed PDFs and unknown jobs return safe, actionable errors; no path traversal.
- Existing `test_binding.py` and other locally discoverable regression tests pass, plus new preflight tests.
- No GitHub Actions required; include local test command and sample report.

### Immediate next action
Implement this read-only preflight on the feature branch, then inspect real sample PDFs locally when available and report measured results. No claims of printed physical quality until physical proofing.

## 13. Feature implementation journal — 2026-11-18
Branch: `feat/read-only-pdf-preflight`. Work is in progress; NOT merged. No existing signature algorithm or PDF export function was changed.

### Committed implementation
- `backend/bookbinder4/preflight.py`: new read-only `analyze_pdf` with page range, target geometry, SHA-256, image placements and effective DPI, links, annotations, text presence, blank candidates and per-page findings. `safe_job_path` validates the existing 16-character hex job ID and constrains lookup to the upload directory.
- `backend/bookbinder4/main.py`: `GET /api/pdf/preflight/{job_id}` endpoint; 404 for unknown jobs, 422 for invalid job IDs/ranges/dimensions.
- `frontend/src/App.tsx`: preliminary paginated advanced-preflight panel (25 pages at a time), warning count, blank candidates, and actionable finding snippets. Requests are aborted on state changes.
- `tests/test_preflight.py`: synthetic tests for source immutability, link/text/blank detection, pagination beyond page 20, invalid job IDs and ranges. HTTP TestClient test intentionally omitted because `httpx` is not declared as a dependency.

### Explicit limits / unfinished acceptance criteria
- Code committed but local tests, frontend build and real PDF evaluation have NOT been executed. Do not mark as production ready.
- Text classification is intentionally conservative: 'text_layer_present_unverified' is not proof of visible vector glyphs. OCR-vs-vector detection is still outstanding.
- Image DPI assumes aspect-preserving fit of the full page into a target rectangle; complex transforms, clipped images, image masks, nested forms, and rotation need additional handling and tests.
- Image inventory relies on PyMuPDF `get_images` and `get_image_rects`; some inline/complex images may not be reported. Add coverage for inline images and annotation/rendering quirks.
- Blank classification is a heuristic (no extracted text/images/drawings) and can miss some content or classify white images as nonblank.
- Source hashing currently reads the entire file into memory; switch to streamed hashing for large books.
- Preflight currently performs page analysis synchronously per API request and may be expensive for large image-heavy PDFs; add caching, resource limits and progress handling.
- UI currently displays a small findings subset per batch; full issue navigation and print-size previews are future work.
- No source modifications, normalization, hyperlink styling removal, enhancement, or case calculations are implemented.

### Next steps
1. Run `python -m pytest tests/test_preflight.py tests/test_binding.py -q` and `cd frontend && npm run build` locally; fix observed failures, not assumed ones.
2. Add image-fixture effective DPI tests and classification tests; address hash streaming and image inventory edge cases.
3. Verify API output against licensed/synthetic image-heavy PDFs, then add per-page evidence and QA export.
4. Keep all changes on this feature branch until regression tests and quality gates pass.

### Continuation — 2026-11-18
- Commit `68e419a`: replaced whole-file `path.read_bytes()` hashing with 1 MiB chunked SHA-256; factored effective-DPI arithmetic into `effective_image_dpi()` with positive-dimension validation.
- Commit `eb5bac7`: added synthetic raster placement/DPI warning test, 1484×1920-to-5.5×8.5-in calculation, streamed hash equivalence, and invalid non-finite target test.
- For 1484×1920 px filling 396×612 pt, effective DPI is ~269.8 horizontal and ~225.9 vertical. Actual page fit can add whitespace and alter placement; the analyzer computes using actual image bounding rectangles.
- Verification status: GitHub source edits committed; tests/build NOT run. Attempt to clone feature branch into local execution environment failed because the environment could not resolve github.com. Do not claim these tests pass.
- Next required work: run tests/build in a checkout with GitHub access, inspect PyMuPDF behavior for inline images/rotated images, harden API errors and upload resource limits, then add complete page warning navigation and machine-readable report export.
