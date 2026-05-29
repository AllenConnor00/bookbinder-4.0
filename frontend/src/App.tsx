import { AlertTriangle, BookOpen, Download, FileSearch, FileUp, Layers, Printer, Settings, Sparkles, ZoomIn, ZoomOut } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

type InspectResult = {
  job_id: string;
  filename: string;
  path: string;
  page_count: number;
  pdf_version: string | null;
  encrypted: boolean;
  warnings: string[];
  preflight: PreflightItem[];
};

type PreflightItem = {
  severity: "ok" | "info" | "warning" | "danger";
  title: string;
  detail: string;
  recommendation: string;
};

type Plan = {
  job_id: string;
  total_source_pages: number;
  total_imposed_pages: number;
  blank_pages: number;
  signatures: { index: number; folios: number; pages: (number | null)[]; sheets: number[] }[];
  sheets: {
    index: number;
    signature_index: number;
    sheet_in_signature: number;
    front: Slot[];
    back: Slot[];
  }[];
  warnings: string[];
};

type Slot = {
  source_page: number | null;
  label: string;
  side: "front" | "back";
  position: "left" | "right";
  rect: [number, number, number, number];
  is_blank: boolean;
};

type SettingsState = {
  binding_mode: "booklet" | "perfect_bound" | "standard" | "custom";
  custom_signature_folios: string;
  standard_signature_folios: number;
  flyleaf: boolean;
  paper: { name: string; width: number; height: number };
  fit_mode: "fit" | "fill" | "stretch";
  source_box: "crop" | "media" | "trim" | "bleed";
  print_safe_margin: number;
  gutter: number;
  creep: number;
  duplex: boolean;
  flip_edge: "short" | "long";
  split_output: "combined" | "by_signature";
  crop_marks: boolean;
  sewing_marks: boolean;
  sewing_station_count: number;
  sewing_station_margin: number;
  sewing_mark_length: number;
  fidelity: "hybrid" | "vector" | "raster";
  raster_dpi: number;
};

const API = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

const defaultSettings: SettingsState = {
  binding_mode: "custom",
  custom_signature_folios: "4",
  standard_signature_folios: 4,
  flyleaf: false,
  paper: { name: "Letter", width: 612, height: 792 },
  fit_mode: "fit",
  source_box: "crop",
  print_safe_margin: 14.2,
  gutter: 0,
  creep: 0,
  duplex: true,
  flip_edge: "short",
  split_output: "by_signature",
  crop_marks: false,
  sewing_marks: false,
  sewing_station_count: 5,
  sewing_station_margin: 56.7,
  sewing_mark_length: 11.3,
  fidelity: "raster",
  raster_dpi: 300,
};

const paperPresets = [
  { name: "Letter", width: 612, height: 792 },
  { name: "Legal", width: 612, height: 1008 },
  { name: "Tabloid", width: 792, height: 1224 },
  { name: "A4", width: 595, height: 842 },
  { name: "A3", width: 842, height: 1191 },
];

export default function App() {
  const [inspect, setInspect] = useState<InspectResult | null>(null);
  const [settings, setSettings] = useState<SettingsState>(defaultSettings);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [sheetIndex, setSheetIndex] = useState(0);
  const [side, setSide] = useState<"front" | "back">("front");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [outputs, setOutputs] = useState<string[]>([]);
  const [previewUrl, setPreviewUrl] = useState("");
  const [zoom, setZoom] = useState(1);

  const requestBody = useMemo(() => (inspect ? { job_id: inspect.job_id, ...settings } : null), [inspect, settings]);

  useEffect(() => {
    if (!requestBody) return;
    const controller = new AbortController();
    const timeout = setTimeout(async () => {
      const response = await fetch(`${API}/api/imposition/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      });
      if (response.ok) {
        setPlan(await response.json());
        setSheetIndex(0);
      }
    }, 150);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [requestBody]);

  useEffect(() => {
    if (!requestBody || !plan) {
      setPreviewUrl("");
      return;
    }
    const controller = new AbortController();
    const timeout = setTimeout(async () => {
      const response = await fetch(`${API}/api/preview/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: requestBody, sheet_index: sheetIndex, side }),
        signal: controller.signal,
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setPreviewUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return url;
        });
      }
    }, 200);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [requestBody, plan, sheetIndex, side]);

  async function uploadPdf(event: FormEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    setBusy(true);
    setMessage("Inspecting PDF...");
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${API}/api/pdf/inspect`, { method: "POST", body });
    if (!response.ok) {
      setMessage("Could not inspect that PDF.");
      setBusy(false);
      return;
    }
    setInspect(await response.json());
    setOutputs([]);
    setMessage("");
    setBusy(false);
  }

  async function exportPdf() {
    if (!requestBody) return;
    setBusy(true);
    setMessage("Generating printable signatures...");
    const response = await fetch(`${API}/api/imposition/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    if (response.ok) {
      const result = await response.json();
      setOutputs(result.output_paths);
      setMessage(result.validation_warnings.length ? result.validation_warnings.join(" ") : "Export complete.");
    } else {
      setMessage("Export failed. Check the backend terminal for details.");
    }
    setBusy(false);
  }

  async function downloadTool(endpoint: string, payload: unknown, filename: string) {
    setBusy(true);
    setMessage(`Creating ${filename}...`);
    const response = await fetch(`${API}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      setMessage(`Could not create ${filename}.`);
      setBusy(false);
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    setMessage(`${filename} created.`);
    setBusy(false);
  }

  function recommendSignatures() {
    if (!inspect) return;
    const pages = inspect.page_count + (settings.flyleaf ? 4 : 0);
    const foliosNeeded = Math.ceil(pages / 4);
    const chunks: number[] = [];
    let remaining = foliosNeeded;
    while (remaining > 0) {
      const next = Math.min(4, remaining);
      chunks.push(next);
      remaining -= next;
    }
    setSettings({ ...settings, binding_mode: "custom", custom_signature_folios: chunks.join(",") });
  }

  const currentSheet = plan?.sheets[sheetIndex];
  const slots = currentSheet ? currentSheet[side] : [];
  const warnings = [...(inspect?.warnings ?? []), ...(plan?.warnings ?? [])];
  const blankLocations = plan?.signatures
    .flatMap((signature) => signature.pages.map((page, index) => (page === null ? `sig ${signature.index + 1} p${index + 1}` : "")))
    .filter(Boolean)
    .slice(0, 12);

  return (
    <main className="app">
      <section className="panel left">
        <div className="brand">
          <BookOpen size={28} />
          <div>
            <h1>Bookbinder 4</h1>
            <p>Local signature imposition for print binding</p>
          </div>
        </div>

        <label className="upload">
          <FileUp size={18} />
          <span>{inspect ? inspect.filename : "Choose PDF"}</span>
          <input type="file" accept="application/pdf,.pdf" onChange={uploadPdf} />
        </label>

        {inspect && (
          <div className="metadata">
            <span>{inspect.page_count} pages</span>
            <span>PDF {inspect.pdf_version ?? "unknown"}</span>
            <span>{inspect.encrypted ? "Encrypted" : "Not encrypted"}</span>
          </div>
        )}

        {inspect && (
          <button className="ghost" onClick={recommendSignatures}>
            <Sparkles size={16} />
            Recommend custom signatures
          </button>
        )}

        <div className="field">
          <label>Binding mode</label>
          <select value={settings.binding_mode} onChange={(e) => setSettings({ ...settings, binding_mode: e.target.value as SettingsState["binding_mode"] })}>
            <option value="custom">Custom folio signatures</option>
            <option value="standard">Standard signatures</option>
            <option value="booklet">Single booklet</option>
            <option value="perfect_bound">Perfect-bound sheets</option>
          </select>
        </div>

        {settings.binding_mode === "custom" && (
          <div className="field">
            <label>Custom folios</label>
            <input value={settings.custom_signature_folios} onChange={(e) => setSettings({ ...settings, custom_signature_folios: e.target.value })} />
            <small>Example: 4,4,3 creates 16, 16, and 12 page signatures.</small>
            {plan && <small>{plan.signatures.map((sig) => `${sig.folios} folios / ${sig.folios * 4} pages`).join(" • ")}</small>}
          </div>
        )}

        {settings.binding_mode === "standard" && (
          <div className="field">
            <label>Folios per signature</label>
            <input type="number" min={1} max={16} value={settings.standard_signature_folios} onChange={(e) => setSettings({ ...settings, standard_signature_folios: Number(e.target.value) })} />
          </div>
        )}

        <div className="toggle">
          <input id="flyleaf" type="checkbox" checked={settings.flyleaf} onChange={(e) => setSettings({ ...settings, flyleaf: e.target.checked })} />
          <label htmlFor="flyleaf">Add front and back flyleaves</label>
        </div>

        <button className="ghost" onClick={() => setAdvanced(!advanced)}>
          <Settings size={16} />
          {advanced ? "Hide advanced settings" : "Show advanced settings"}
        </button>

        {advanced && <AdvancedSettings settings={settings} setSettings={setSettings} />}
      </section>

      <section className="panel preview">
        <div className="previewHeader">
          <div>
            <h2>Sheet preview</h2>
            <p>{currentSheet ? `Signature ${currentSheet.signature_index + 1}, sheet ${currentSheet.sheet_in_signature + 1}` : "Choose a PDF to begin"}</p>
          </div>
          <div className="segmented">
            <button className={side === "front" ? "active" : ""} onClick={() => setSide("front")}>Front</button>
            <button className={side === "back" ? "active" : ""} onClick={() => setSide("back")}>Back</button>
          </div>
        </div>

        <div className="previewTools">
          <button className="ghost" disabled={!plan || sheetIndex === 0} onClick={() => setSheetIndex(Math.max(0, sheetIndex - 1))}>Previous</button>
          <button className="ghost" disabled={!plan || sheetIndex >= (plan.sheets.length - 1)} onClick={() => plan && setSheetIndex(Math.min(plan.sheets.length - 1, sheetIndex + 1))}>Next</button>
          <button className="iconButton" onClick={() => setZoom(Math.max(0.75, zoom - 0.25))} title="Zoom out"><ZoomOut size={17} /></button>
          <button className="iconButton" onClick={() => setZoom(Math.min(2, zoom + 0.25))} title="Zoom in"><ZoomIn size={17} /></button>
        </div>

        <div className="sheetWrap">
        <div className="sheet" style={{ transform: `scale(${zoom})` }}>
          {previewUrl && <img className="renderedPreview" src={previewUrl} alt="Rendered imposed PDF sheet preview" />}
          {slots.map((slot) => (
            <div key={`${slot.side}-${slot.position}`} className={`pageSlot ${slot.position}`}>
              <span>{slot.label}</span>
              <small>{slot.is_blank ? "Blank" : `Source page ${slot.source_page}`}</small>
            </div>
          ))}
        </div>
        </div>

        {plan && (
          <div className="sheetNav">
            <input type="range" min={0} max={Math.max(0, plan.sheets.length - 1)} value={sheetIndex} onChange={(e) => setSheetIndex(Number(e.target.value))} />
            <span>{sheetIndex + 1} / {plan.sheets.length} sheets</span>
          </div>
        )}
      </section>

      <section className="panel right">
        <div className="summaryCard">
          <Layers size={22} />
          <div>
            <h2>Output summary</h2>
            <p>{plan ? `${plan.signatures.length} signatures, ${plan.sheets.length} sheets, ${plan.blank_pages} blanks` : "No plan yet"}</p>
          </div>
        </div>

        {inspect && (
          <div className="preflight">
            <h3><FileSearch size={17} /> PDF health check</h3>
            {inspect.preflight.map((item) => (
              <div className={`preflightItem ${item.severity}`} key={`${item.title}-${item.detail}`}>
                <strong>{item.title}</strong>
                <span>{item.detail}</span>
                <small>{item.recommendation}</small>
              </div>
            ))}
          </div>
        )}

        {blankLocations && blankLocations.length > 0 && (
          <div className="blankList">
            <h3>Blank page locations</h3>
            <p>{blankLocations.join(", ")}{plan && plan.blank_pages > blankLocations.length ? "..." : ""}</p>
          </div>
        )}

        <div className="warnings">
          {warnings.map((warning, index) => (
            <div className="warning" key={`${warning}-${index}`}>
              <AlertTriangle size={16} />
              <span>{warning}</span>
            </div>
          ))}
        </div>

        <button className="primary" disabled={!inspect || busy} onClick={exportPdf}>
          <Download size={18} />
          {busy ? "Working..." : "Export printable PDFs"}
        </button>

        <button className="ghost" disabled={!requestBody || busy} onClick={() => requestBody && downloadTool("/api/preview/contact-sheet", { settings: requestBody }, "bookbinder4-preview-contact-sheet.pdf")}>
          <FileSearch size={16} />
          Export preview contact sheet
        </button>

        <button className="ghost" disabled={busy} onClick={() => downloadTool("/api/tools/calibration", { paper: settings.paper, print_safe_margin: settings.print_safe_margin }, "bookbinder4-printer-calibration.pdf")}>
          <Printer size={16} />
          Print calibration page
        </button>

        {message && <p className="message">{message}</p>}

        {outputs.length > 0 && (
          <div className="outputs">
            <h3>Generated files</h3>
            {outputs.map((path) => (
              <code key={path}>{path}</code>
            ))}
          </div>
        )}

        <div className="tip">
          <Sparkles size={18} />
          <span>Safest print mode fully flattens pages, which is the reliability-first choice for difficult PDFs.</span>
        </div>
      </section>
    </main>
  );
}

function AdvancedSettings({ settings, setSettings }: { settings: SettingsState; setSettings: (settings: SettingsState) => void }) {
  return (
    <div className="advanced">
      <div className="field">
        <label>Paper size</label>
        <select
          value={settings.paper.name}
          onChange={(e) => setSettings({ ...settings, paper: paperPresets.find((paper) => paper.name === e.target.value) ?? settings.paper })}
        >
          {paperPresets.map((paper) => (
            <option key={paper.name} value={paper.name}>{paper.name}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>Fit mode</label>
        <select value={settings.fit_mode} onChange={(e) => setSettings({ ...settings, fit_mode: e.target.value as SettingsState["fit_mode"] })}>
          <option value="fit">Fit inside page area</option>
          <option value="fill">Fill page area</option>
          <option value="stretch">Stretch to page area</option>
        </select>
      </div>
      <div className="field">
        <label>PDF box</label>
        <select value={settings.source_box} onChange={(e) => setSettings({ ...settings, source_box: e.target.value as SettingsState["source_box"] })}>
          <option value="crop">CropBox</option>
          <option value="media">MediaBox</option>
          <option value="trim">TrimBox</option>
          <option value="bleed">BleedBox</option>
        </select>
      </div>
      <div className="field">
        <label>Print-safe margin</label>
        <input
          type="number"
          min={0}
          max={25}
          step={0.5}
          value={Number((settings.print_safe_margin / 2.83464567).toFixed(1))}
          onChange={(e) => setSettings({ ...settings, print_safe_margin: Number(e.target.value) * 2.83464567 })}
        />
        <small>Use 5 mm for the HP Color LaserJet Pro M255dw.</small>
      </div>
      <div className="field two">
        <label>Gutter</label>
        <input type="number" value={settings.gutter} onChange={(e) => setSettings({ ...settings, gutter: Number(e.target.value) })} />
        <label>Creep</label>
        <input type="number" value={settings.creep} onChange={(e) => setSettings({ ...settings, creep: Number(e.target.value) })} />
      </div>
      <div className="field">
        <label>Fidelity</label>
        <select value={settings.fidelity} onChange={(e) => setSettings({ ...settings, fidelity: e.target.value as SettingsState["fidelity"] })}>
          <option value="raster">Safest print / flattened</option>
          <option value="hybrid">Hybrid / flattened preview</option>
          <option value="vector">Best quality / preserve vectors</option>
        </select>
      </div>
      <div className="field">
        <label>Flattening DPI</label>
        <input type="number" min={72} max={600} value={settings.raster_dpi} onChange={(e) => setSettings({ ...settings, raster_dpi: Number(e.target.value) })} />
        <small>Use 300 DPI for normal quality, 450-600 DPI for sharper art and text if larger files are acceptable.</small>
      </div>
      <div className="toggle">
        <input id="combined" type="checkbox" checked={settings.split_output === "combined"} onChange={(e) => setSettings({ ...settings, split_output: e.target.checked ? "combined" : "by_signature" })} />
        <label htmlFor="combined">Export one combined PDF</label>
      </div>
      <div className="toggle">
        <input id="marks" type="checkbox" checked={settings.crop_marks} onChange={(e) => setSettings({ ...settings, crop_marks: e.target.checked })} />
        <label htmlFor="marks">Add crop marks</label>
      </div>
      <div className="toggle">
        <input id="sewingMarks" type="checkbox" checked={settings.sewing_marks} onChange={(e) => setSettings({ ...settings, sewing_marks: e.target.checked })} />
        <label htmlFor="sewingMarks">Add sewing hole marks</label>
      </div>
      {settings.sewing_marks && (
        <div className="field two">
          <label>Hole count</label>
          <input
            type="number"
            min={2}
            max={12}
            value={settings.sewing_station_count}
            onChange={(e) => setSettings({ ...settings, sewing_station_count: Number(e.target.value) })}
          />
          <label>Head/tail offset mm</label>
          <input
            type="number"
            min={0}
            max={75}
            step={1}
            value={Number((settings.sewing_station_margin / 2.83464567).toFixed(0))}
            onChange={(e) => setSettings({ ...settings, sewing_station_margin: Number(e.target.value) * 2.83464567 })}
          />
          <label>Tick length mm</label>
          <input
            type="number"
            min={1}
            max={13}
            step={0.5}
            value={Number((settings.sewing_mark_length / 2.83464567).toFixed(1))}
            onChange={(e) => setSettings({ ...settings, sewing_mark_length: Number(e.target.value) * 2.83464567 })}
          />
        </div>
      )}
    </div>
  );
}
