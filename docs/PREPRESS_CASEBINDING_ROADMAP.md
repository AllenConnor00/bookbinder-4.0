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
