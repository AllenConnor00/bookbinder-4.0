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
  flyleaf_pages: number;
  padding_blank_pages: number;
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
  flyleaf: boolean | null;
  flyleaf_arrangement: "none" | "single" | "double";
  front_flyleaf_leaves: number;
  back_flyleaf_leaves: number;
  paper: { name: string; width: number; height: number };
  fit_mode: "fit" | "fill" | "stretch";
  source_box: "crop" | "media" | "trim" | "bleed";
  print_safe_margin: number;
  gutter: number;
  creep: number;
  duplex: boolean;
  flip_edge: "short" | "long";
  book_type: "custom" | "practice" | "general_hardcover" | "trpg_reference" | "deluxe_tome";
  sewing_layout: "custom" | "unsupported_3" | "unsupported_5" | "two_tape" | "three_tape";
  split_output: "combined" | "by_signature";
  crop_marks: boolean;
  sewing_marks: boolean;
  sewing_debug_marks: boolean;
  sewing_station_count: number;
  sewing_station_margin: number;
  sewing_mark_length: number;
  tape_supports: boolean;
  tape_count: number;
  tape_width: number;
  project_name: string | null;
  fidelity: "vector" | "raster" | "auto";
  raster_dpi: number;
  auto_validation_dpi: number;
  auto_diff_threshold: number;
  auto_diff_mode: "rmse" | "pixel";
  manual_raster_pages: number[];
  manual_vector_pages: number[];
};

type ExportReport = {
  fidelity: "vector" | "raster" | "auto";
  total_slots: number;
  vector_slots: number;
  raster_slots: number;
  auto_validated_pages: number;
  raster_fallback_pages: number[];
  manual_raster_pages: number[];
  manual_vector_pages: number[];
  warnings: string[];
};

const API = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const PT_PER_MM = 72 / 25.4;

const defaultSettings: SettingsState = {
  binding_mode: "custom",
  custom_signature_folios: "4",
  standard_signature_folios: 4,
  flyleaf: null,
  flyleaf_arrangement: "double",
  front_flyleaf_leaves: 2,
  back_flyleaf_leaves: 2,
  paper: { name: "Letter", width: 612, height: 792 },
  fit_mode: "fit",
  source_box: "crop",
  print_safe_margin: 14.2,
  gutter: 0,
  creep: 0,
  duplex: true,
  flip_edge: "short",
  book_type: "custom",
  sewing_layout: "three_tape",
  split_output: "by_signature",
  crop_marks: false,
  sewing_marks: false,
  sewing_debug_marks: false,
  sewing_station_count: 5,
  sewing_station_margin: 20 * PT_PER_MM,
  sewing_mark_length: 11.3,
  tape_supports: true,
  tape_count: 3,
  tape_width: 6 * PT_PER_MM,
  project_name: null,
  fidelity: "auto",
  raster_dpi: 600,
  auto_validation_dpi: 150,
  auto_diff_threshold: 3,
  auto_diff_mode: "rmse",
  manual_raster_pages: [],
  manual_vector_pages: [],
};

const paperPresets = [
  { name: "Letter", width: 612, height: 792 },
  { name: "Legal", width: 612, height: 1008 },
  { name: "Tabloid", width: 792, height: 1224 },
  { name: "A4", width: 595, height: 842 },
  { name: "A3", width: 842, height: 1191 },
];

const bookTypePresets = {
  custom: {
    label: "Manual / custom",
    guidance: "Keep full manual control over signature and sewing choices.",
    settings: {},
  },
  practice: {
    label: "Practice book",
    guidance: "Good for learning: 4-sheet signatures and simple sewing are usually enough.",
    settings: { sewing_layout: "unsupported_5", tape_supports: false, tape_count: 0, ...flyleafSettingsForArrangement("single") },
  },
  general_hardcover: {
    label: "Novel / general hardcover",
    guidance: "A durable everyday hardcover usually works well with 4-sheet signatures, double flyleaves, and tape-supported sewing.",
    settings: { sewing_layout: "three_tape", tape_supports: true, tape_count: 3, ...flyleafSettingsForArrangement("double") },
  },
  trpg_reference: {
    label: "TRPG / reference hardcover",
    guidance: "For books left open on tables, consider 3 tape supports and mull reinforcement on the spine.",
    settings: { sewing_layout: "three_tape", tape_supports: true, tape_count: 3, ...flyleafSettingsForArrangement("double") },
  },
  deluxe_tome: {
    label: "Deluxe leather-bound tome",
    guidance: "For premium bindings, consider sewing on tapes, a rounded spine, reinforced hinges, and careful casing-in.",
    settings: { sewing_layout: "three_tape", tape_supports: true, tape_count: 3, ...flyleafSettingsForArrangement("double") },
  },
} as const;

const sewingLayoutPresets = {
  custom: "Custom",
  unsupported_3: "Unsupported sewing - 3 stations",
  unsupported_5: "Unsupported sewing - 5 stations",
  two_tape: "Two tape supports",
  three_tape: "Three tape supports",
} as const;

function parsePageList(value: string) {
  return value
    .split(/[,\s]+/)
    .map((part) => Number(part.trim()))
    .filter((page) => Number.isInteger(page) && page > 0);
}

function flyleafSettingsForArrangement(arrangement: SettingsState["flyleaf_arrangement"]) {
  const leaves = arrangement === "none" ? 0 : arrangement === "single" ? 1 : 2;
  return {
    flyleaf_arrangement: arrangement,
    front_flyleaf_leaves: leaves,
    back_flyleaf_leaves: leaves,
    flyleaf: leaves > 0,
  };
}

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
  const [exportReport, setExportReport] = useState<ExportReport | null>(null);
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
    setExportReport(null);
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
      const report = result.export_report as ExportReport | null;
      setExportReport(report);
      const reportSummary = report ? ` ${report.vector_slots} vector slot(s), ${report.raster_slots} raster fallback slot(s).` : "";
      setMessage(result.validation_warnings.length ? result.validation_warnings.join(" ") : `Export complete.${reportSummary}`);
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

  async function recommendSignatures() {
    if (!inspect) return;
    setBusy(true);
    setMessage("Recommending signatures...");
    const folios = await getRecommendedFolios();
    if (folios.length) {
      setSettings({ ...settings, binding_mode: "custom", custom_signature_folios: folios.join(",") });
      setMessage(`Recommended signatures: ${folios.join(",")}`);
    } else {
      setMessage("Could not recommend signatures.");
    }
    setBusy(false);
  }

  async function getRecommendedFolios() {
    if (!inspect) return [];
    const response = await fetch(`${API}/api/imposition/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        total_pages: inspect.page_count,
        flyleaf_arrangement: settings.flyleaf_arrangement,
        front_flyleaf_leaves: settings.front_flyleaf_leaves,
        back_flyleaf_leaves: settings.back_flyleaf_leaves,
        preferred: 4,
        max_folios: 5,
        avoid_one: true,
      }),
    });
    if (response.ok) {
      const result = await response.json();
      return result.folios as number[];
    }
    return [];
  }

  async function applyBookTypePreset() {
    setBusy(true);
    const preset = bookTypePresets[settings.book_type];
    const presetSewingLayout = "sewing_layout" in preset.settings ? preset.settings.sewing_layout : settings.sewing_layout;
    const folios = inspect ? await getRecommendedFolios() : [];
    setSettings({
      ...settings,
      ...preset.settings,
      binding_mode: folios.length ? "custom" : settings.binding_mode,
      custom_signature_folios: folios.length ? folios.join(",") : settings.custom_signature_folios,
      standard_signature_folios: 4,
      sewing_station_count: presetSewingLayout === "unsupported_3" ? 3 : 5,
      sewing_station_margin: 20 * PT_PER_MM,
      tape_width: 6 * PT_PER_MM,
    } as SettingsState);
    setMessage(folios.length ? `Applied ${preset.label} guidance with signatures: ${folios.join(",")}` : `Applied ${preset.label} guidance.`);
    setBusy(false);
  }

  const currentSheet = plan?.sheets[sheetIndex];
  const slots = currentSheet ? currentSheet[side] : [];
  const warnings = [...(inspect?.warnings ?? []), ...(plan?.warnings ?? [])];
  const hasOneFolioSignature = Boolean(plan?.signatures.some((signature) => signature.folios === 1) && plan.signatures.length > 1);
  const bookTypeGuidance = bookTypePresets[settings.book_type].guidance;
  const guidance = [
    hasOneFolioSignature ? "One-sheet signatures are generally less desirable for durable sewn hardcovers. Use Recommend custom signatures if you want the planner to redistribute sheets." : "",
    settings.book_type === "trpg_reference" ? "TRPG/reference books benefit from tape supports and mull because they are opened repeatedly and left flat on tables." : "",
    settings.book_type === "deluxe_tome" ? "Deluxe leather-bound books often benefit from rounded spine construction, reinforced hinges, and premium covering materials." : "",
    settings.sewing_layout === "two_tape" || settings.sewing_layout === "three_tape" ? "Tape support zones will appear on the punching template as placement guides." : "",
  ].filter(Boolean);
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
          <label>Book type</label>
          <select value={settings.book_type} onChange={(e) => setSettings({ ...settings, book_type: e.target.value as SettingsState["book_type"] })}>
            {Object.entries(bookTypePresets).map(([key, preset]) => (
              <option key={key} value={key}>{preset.label}</option>
            ))}
          </select>
          <small>{bookTypeGuidance}</small>
        </div>

        {settings.book_type !== "custom" && (
          <button className="ghost" onClick={applyBookTypePreset} disabled={busy}>
            <Sparkles size={16} />
            Apply book type recommendations
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

        <div className="field">
          <label>Flyleaves</label>
          <select value={settings.flyleaf_arrangement} onChange={(e) => setSettings({ ...settings, ...flyleafSettingsForArrangement(e.target.value as SettingsState["flyleaf_arrangement"]) })}>
            <option value="none">None</option>
            <option value="single">Single flyleaf</option>
            <option value="double">Double flyleaf</option>
          </select>
          <small>Double flyleaves are recommended for premium hardcovers, custom endpapers, and leather-bound editions.</small>
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
            <p>{plan ? `${plan.signatures.length} signatures, ${plan.sheets.length} sheets, ${plan.total_imposed_pages} imposed pages` : "No plan yet"}</p>
          </div>
        </div>

        {plan && (
          <div className="preflight">
            <h3><Layers size={17} /> Page count</h3>
            <div className="preflightItem info">
              <strong>{plan.total_source_pages} content page(s)</strong>
              <span>{plan.flyleaf_pages} flyleaf page(s), {plan.padding_blank_pages} padding page(s)</span>
              <small>{plan.total_imposed_pages} final imposed page(s). Signature layout: {plan.signatures.map((sig) => `${sig.folios}`).join(", ")} folded sheet(s).</small>
            </div>
          </div>
        )}

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

        {guidance.length > 0 && (
          <div className="preflight">
            <h3><Sparkles size={17} /> Binding guidance</h3>
            {guidance.map((item) => (
              <div className="preflightItem info" key={item}>
                <span>{item}</span>
              </div>
            ))}
          </div>
        )}

        <button className="primary" disabled={!inspect || busy} onClick={exportPdf}>
          <Download size={18} />
          {busy ? "Working..." : "Export printable PDFs"}
        </button>

        <button className="ghost" disabled={!requestBody || busy} onClick={() => requestBody && downloadTool("/api/preview/contact-sheet", { settings: requestBody }, "bookbinder4-preview-contact-sheet.pdf")}>
          <FileSearch size={16} />
          Export preview contact sheet
        </button>

        <button className="ghost" disabled={!requestBody || busy} onClick={() => requestBody && downloadTool("/api/tools/punching-template", { settings: requestBody }, "bookbinder4-punching-template.pdf")}>
          <Printer size={16} />
          Export punching template
        </button>

        <button className="ghost" disabled={busy} onClick={() => downloadTool("/api/tools/calibration", { paper: settings.paper, print_safe_margin: settings.print_safe_margin, flip_edge: settings.flip_edge }, "bookbinder4-printer-calibration.pdf")}>
          <Printer size={16} />
          Print calibration page
        </button>

        {message && <p className="message">{message}</p>}

        {exportReport && (
          <div className="preflight">
            <h3><FileSearch size={17} /> Export report</h3>
            <div className="preflightItem info">
              <strong>{exportReport.fidelity === "auto" ? "Auto / Best Quality" : exportReport.fidelity}</strong>
              <span>{exportReport.total_slots} total slot(s), {exportReport.vector_slots} vector, {exportReport.raster_slots} raster fallback.</span>
              <small>{exportReport.auto_validated_pages} source page(s) validated.</small>
            </div>
            {(exportReport.raster_fallback_pages.length > 0 || exportReport.manual_raster_pages.length > 0 || exportReport.manual_vector_pages.length > 0) && (
              <div className="preflightItem warning">
                <strong>Fallbacks and overrides</strong>
                <span>{exportReport.raster_fallback_pages.length ? `Raster fallback pages: ${exportReport.raster_fallback_pages.join(", ")}` : "No automatic raster fallbacks."}</span>
                <small>
                  {[
                    exportReport.manual_raster_pages.length ? `Forced raster: ${exportReport.manual_raster_pages.join(", ")}` : "",
                    exportReport.manual_vector_pages.length ? `Forced vector: ${exportReport.manual_vector_pages.join(", ")}` : "",
                  ].filter(Boolean).join(" ")}
                </small>
              </div>
            )}
          </div>
        )}

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
          <span>For booklet signatures, print duplex at 100% / Actual Size and use flip on short edge unless your printer proves otherwise.</span>
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
      <div className="field two">
        <label>Front flyleaf leaves</label>
        <input type="number" min={0} max={8} value={settings.front_flyleaf_leaves} onChange={(e) => setSettings({ ...settings, front_flyleaf_leaves: Number(e.target.value), flyleaf: Number(e.target.value) > 0 || settings.back_flyleaf_leaves > 0 })} />
        <label>Back flyleaf leaves</label>
        <input type="number" min={0} max={8} value={settings.back_flyleaf_leaves} onChange={(e) => setSettings({ ...settings, back_flyleaf_leaves: Number(e.target.value), flyleaf: settings.front_flyleaf_leaves > 0 || Number(e.target.value) > 0 })} />
      </div>
      <div className="field">
        <label>Print-safe margin</label>
        <input
          type="number"
          min={0}
          max={25}
          step={0.5}
          value={Number((settings.print_safe_margin / PT_PER_MM).toFixed(1))}
          onChange={(e) => setSettings({ ...settings, print_safe_margin: Number(e.target.value) * PT_PER_MM })}
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
          <option value="auto">Auto / Best Quality</option>
          <option value="vector">Vector / sharpest</option>
          <option value="raster">Raster / safest appearance</option>
        </select>
        <small>
          {settings.fidelity === "auto" && "Recommended: keeps pages vector unless validation finds visual differences."}
          {settings.fidelity === "vector" && "Sharpest text and line art; complex PDF effects may be missed by some processors."}
          {settings.fidelity === "raster" && "Flattens every source page slot for compatibility; text and vectors become softer images."}
        </small>
      </div>
      <div className="field">
        <label>Raster fallback DPI</label>
        <input type="number" min={72} max={600} value={settings.raster_dpi} onChange={(e) => setSettings({ ...settings, raster_dpi: Number(e.target.value) })} />
        <small>Auto and Raster use this for final flattened fallback pages; 600 DPI preserves small text better.</small>
      </div>
      {settings.fidelity === "auto" && (
        <>
          <div className="field two">
            <label>Validation DPI</label>
            <input type="number" min={72} max={300} value={settings.auto_validation_dpi} onChange={(e) => setSettings({ ...settings, auto_validation_dpi: Number(e.target.value) })} />
            <label>Diff threshold</label>
            <input type="number" min={0} max={100} step={0.25} value={settings.auto_diff_threshold} onChange={(e) => setSettings({ ...settings, auto_diff_threshold: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Diff mode</label>
            <select value={settings.auto_diff_mode} onChange={(e) => setSettings({ ...settings, auto_diff_mode: e.target.value as SettingsState["auto_diff_mode"] })}>
              <option value="rmse">RMSE</option>
              <option value="pixel">Changed pixel percent</option>
            </select>
          </div>
          <div className="field">
            <label>Force raster pages</label>
            <input value={settings.manual_raster_pages.join(", ")} onChange={(e) => setSettings({ ...settings, manual_raster_pages: parsePageList(e.target.value) })} />
            <small>Comma-separated source page numbers for known-problem pages.</small>
          </div>
          <div className="field">
            <label>Force vector pages</label>
            <input value={settings.manual_vector_pages.join(", ")} onChange={(e) => setSettings({ ...settings, manual_vector_pages: parsePageList(e.target.value) })} />
            <small>Comma-separated source page numbers that should stay vector even if validation differs.</small>
          </div>
        </>
      )}
      <div className="field">
        <label>Project name</label>
        <input value={settings.project_name ?? ""} onChange={(e) => setSettings({ ...settings, project_name: e.target.value || null })} />
      </div>
      <div className="field">
        <label>Duplex flip</label>
        <select value={settings.flip_edge} onChange={(e) => setSettings({ ...settings, flip_edge: e.target.value as SettingsState["flip_edge"] })}>
          <option value="short">Short edge</option>
          <option value="long">Long edge</option>
        </select>
        <small>Booklet signatures on landscape sheets usually use short-edge duplex.</small>
      </div>
      <div className="field">
        <label>Sewing layout</label>
        <select value={settings.sewing_layout} onChange={(e) => setSettings({ ...settings, sewing_layout: e.target.value as SettingsState["sewing_layout"] })}>
          {Object.entries(sewingLayoutPresets).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <small>Layout presets guide punching templates; custom station controls stay available.</small>
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
        <label htmlFor="sewingMarks">Add sewing hole marks to imposed sheets</label>
      </div>
      <div className="toggle">
        <input id="debugSewingMarks" type="checkbox" checked={settings.sewing_debug_marks} onChange={(e) => setSettings({ ...settings, sewing_debug_marks: e.target.checked })} />
        <label htmlFor="debugSewingMarks">Debug sewing marks on imposed sheets</label>
      </div>
      {(settings.sewing_marks || settings.sewing_debug_marks || settings.sewing_layout === "custom") && (
        <div className="field two">
          <label>Hole count</label>
          <input
            type="number"
            min={2}
            max={12}
            value={settings.sewing_station_count}
            onChange={(e) => setSettings({ ...settings, sewing_station_count: Number(e.target.value) })}
            disabled={settings.sewing_layout !== "custom"}
          />
          <label>Head/tail offset mm</label>
          <input
            type="number"
            min={0}
            max={75}
            step={1}
            value={Number((settings.sewing_station_margin / PT_PER_MM).toFixed(0))}
            onChange={(e) => setSettings({ ...settings, sewing_station_margin: Number(e.target.value) * PT_PER_MM })}
          />
          <label>Tick length mm</label>
          <input
            type="number"
            min={1}
            max={13}
            step={0.5}
            value={Number((settings.sewing_mark_length / PT_PER_MM).toFixed(1))}
            onChange={(e) => setSettings({ ...settings, sewing_mark_length: Number(e.target.value) * PT_PER_MM })}
          />
        </div>
      )}
      <div className="toggle">
        <input id="tapeSupports" type="checkbox" checked={settings.tape_supports} onChange={(e) => setSettings({ ...settings, tape_supports: e.target.checked })} />
        <label htmlFor="tapeSupports">Show tape support zones on template</label>
      </div>
      {settings.tape_supports && (
        <div className="field two">
          <label>Tape count</label>
          <input type="number" min={0} max={6} value={settings.tape_count} onChange={(e) => setSettings({ ...settings, tape_count: Number(e.target.value) })} />
          <label>Tape width mm</label>
          <input
            type="number"
            min={0}
            max={25}
            step={0.5}
            value={Number((settings.tape_width / PT_PER_MM).toFixed(1))}
            onChange={(e) => setSettings({ ...settings, tape_width: Number(e.target.value) * PT_PER_MM })}
          />
        </div>
      )}
    </div>
  );
}
