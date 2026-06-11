# Bookbinder 4

Bookbinder 4 is a local-only web app for generating printable bookbinding signatures from PDFs. It replaces the legacy Jython/Swing/iText app with a modern React UI and a FastAPI/PyMuPDF backend.

## Run

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Start the app:

```bash
python3 scripts/dev.py
```

Open `http://127.0.0.1:5173`.

## Workflow

1. Choose a PDF.
2. Pick custom folio signatures, such as `4,4,3`.
3. Review the PDF health check, rendered sheet preview, blank page locations, and export report.
4. Use the calibration page if you need printer alignment help.
5. Optionally export a preview contact sheet.
6. Export printable PDFs.

Generated PDFs are written under `outputs/<job-id>/`.

## Hardcover Binding Workflow

For a sewn hardcover on letter paper:

1. Export by signature and print duplex at 100% / Actual Size.
2. Keep each signature in order as it comes off the printer.
3. Fold every sheet exactly on the centerline, then nest the sheets for each signature.
4. If using printed sewing marks, pierce each signature on the fold at the marked stations.
5. Sew the signatures together with kettle stitches at the head and tail.
6. Press the sewn text block flat, glue the spine, and add mull/super and endpapers.
7. Trim only if needed, then case the text block into hardcover boards.

For tabletop books, 4 folios per signature is a good starting point on ordinary letter paper. Use Auto / Best Quality fidelity, a 5 mm print-safe margin for the M255dw, double flyleaves for hardcover endpaper structure, and tape-supported sewing with 5 functional stations about 20 mm from the head and tail.

## Notes

- Auto / Best Quality fidelity is the default. It validates source pages against a raster reference, keeps visually equivalent pages vector, and rasterizes only fallback pages.
- Vector / sharpest always preserves PDF source pages as vector objects with `show_pdf_page`, but complex PDF effects may not print exactly in every processor.
- Raster / safest appearance rasterizes every source page slot. It is still available as an emergency compatibility option, but it creates softer text and larger PDFs.
- Auto validation uses a lower DPI comparison for speed. Final raster fallback uses Raster fallback DPI, which defaults to 600 for sharper small text and colored table elements.
- Double flyleaves are the default for hardcover-oriented work: 2 blank leaves / 4 pages before content and 2 blank leaves / 4 pages after content.
- Standard signatures default to 4 folded sheets / 16 pages and avoid a final 1-sheet signature when practical.
- Sewing defaults favor 3 tape supports with 5 functional stations for durable cloth-bound, TRPG/reference, and premium hardcover construction.
- Print-safe margin defaults to 5 mm for laser printers such as the HP Color LaserJet Pro M255dw.
- Creep, gutter, crop marks, sewing hole marks, PDF page-box selection, and output splitting are available in advanced settings.
- The original sample PDF and legacy generated files are kept for regression testing.

## Flyleaves

A flyleaf is a blank leaf between the pastedown/endpaper and the printed content. One leaf has two pages: recto and verso.

- None: no intentional flyleaf blanks are added.
- Single flyleaf: 1 blank leaf / 2 pages at the front and 1 blank leaf / 2 pages at the back.
- Double flyleaf: 2 blank leaves / 4 pages at the front and 2 blank leaves / 4 pages at the back.

Double flyleaves are useful for premium hardcovers, custom endpapers, leather-bound editions, and books where you want a more traditional buffer between decorative endpapers and printed content. Flyleaf pages are inserted before normal signature padding, so the export summary separates content pages, flyleaf pages, padding blank pages, and final imposed page count.

## Auto Fidelity Report

Exports return a human-readable report in the app:

```text
Auto / Best Quality
12 total slot(s), 10 vector, 2 raster fallback.
8 source page(s) validated.
Raster fallback pages: 14, 22
Forced raster: 30
Forced vector: 7
```

Use this report to confirm that text-heavy pages stayed vector while pages with missing fills, transparency, annotations, forms, or complex graphics fell back to high-DPI raster.

## Manual Fidelity Testing

1. Export a text-only PDF in Auto mode and confirm the report shows vector slots and no raster fallback pages.
2. Export a PDF with colored table fills or transparency in Auto mode and inspect the raster fallback page list.
3. Add a known-problem source page to Force raster pages and confirm only slots using that page are rasterized.
4. Re-export with Vector mode to compare sharpness and with Raster mode to compare visual compatibility.
