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
3. Review the PDF health check, rendered sheet preview, and blank page locations.
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

For tabletop books, 4 folios per signature is a good starting point on ordinary letter paper. Use full flattening for reliability, a 5 mm print-safe margin for the M255dw, and sewing marks with 5 stations about 20 mm from the head and tail.

## Notes

- Safest print / flattened fidelity is the default. It rasterizes pages at 300 DPI before imposition so difficult PDFs print as reliably as possible.
- For sharper art or small text, raise Flattening DPI to 450 or 600. This creates larger PDFs and slower exports.
- Best quality / preserve vectors is available in advanced settings when searchable/vector output matters more than maximum print predictability.
- Print-safe margin defaults to 5 mm for laser printers such as the HP Color LaserJet Pro M255dw.
- Creep, gutter, crop marks, sewing hole marks, PDF page-box selection, and output splitting are available in advanced settings.
- The original sample PDF and legacy generated files are kept for regression testing.
