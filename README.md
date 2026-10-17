# Bookbinder 4

A local-first PDF imposition application for preparing printable bookbinding signatures. The repository includes a React/Vite frontend and a Python backend.

Bookbinder 4 is a modern reimplementation and extension of the legacy **Bookbinder 3** desktop application. The current application replaces the older Java/Jython-era workflow with a **React frontend** and **FastAPI/PyMuPDF backend**, while preserving the specialized PDF-imposition workflow that made the original project useful.

> **Project provenance:** The repository retains the original Bookbinder 3 archive for reference and regression testing. The original project's `readme.txt` credits its author and the iText/JPedal libraries used by the legacy application. Bookbinder 4 is my modernization of that application rather than a claim of authorship over the original Bookbinder 3 code. No new license is asserted here over the retained legacy source.

## What Bookbinder 4 Does

- Generates printable signatures from arbitrary PDFs
- Supports custom folio patterns such as `4,4,3`
- Performs PDF health checks before imposition
- Provides rendered sheet previews and blank-page visibility
- Includes printer calibration and print-safe margin controls
- Supports creep, gutter, crop marks, and sewing-hole marks
- Can prioritize maximum print reliability through page flattening
- Can preserve vector/searchable content when print fidelity allows
- Exports individual signatures or complete print-ready PDFs

## Architecture

**Frontend:** React  
**Backend:** FastAPI / Python  
**PDF processing:** PyMuPDF  
**Testing:** Regression tests against legacy/sample documents  
**Deployment model:** Local-first web application

The application intentionally runs locally: source PDFs and generated book files do not need to be uploaded to an external service.

## Run Locally

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Start the application:

```bash
python3 scripts/dev.py
```

Then open:

```text
http://127.0.0.1:5173
```

## Typical Workflow

1. Choose a PDF.
2. Select a signature pattern.
3. Review the PDF health check, sheet preview, and blank-page locations.
4. Calibrate for the target printer when necessary.
5. Configure advanced imposition options if needed.
6. Export print-ready signatures.
7. Print duplex at **100% / Actual Size**.

Generated PDFs are written under `outputs/<job-id>/`.

## Print & Binding Features

For sewn hardcover books, Bookbinder 4 can produce signatures with configurable sewing marks and print-safe margins. Advanced controls include:

- Signature size and folio patterns
- Creep compensation
- Gutter adjustment
- Crop marks
- Sewing-hole marks
- PDF page-box selection
- Output splitting
- Configurable raster flattening
- Vector-preserving output

The default flattened workflow rasterizes difficult PDFs before imposition to maximize predictable printing. Higher DPI values improve small text and artwork at the cost of larger output files and slower processing.

## Legacy Bookbinder 3

The repository currently contains the original Bookbinder 3 materials alongside the new implementation so behavior can be compared during development. These include the original JAR, source tree, and `readme.txt`.

The original README identifies the legacy Bookbinder project and credits the third-party libraries on which it was built. Those files are retained with their original attribution.

## Verification and limitations

The repository documents regression testing against sample and legacy documents, but this README review has not independently executed those tests or verified printer output. Printed results depend on printer calibration, paper handling, duplex settings, and the characteristics of the source PDF.

## Status

Bookbinder 4 is an active modernization project. The current focus is reliable local PDF processing, predictable physical printing, and making specialized book-imposition tooling substantially easier to use through a modern browser interface.
