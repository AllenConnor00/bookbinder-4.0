from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BindingMode(str, Enum):
    booklet = "booklet"
    perfect_bound = "perfect_bound"
    standard = "standard"
    custom = "custom"


class FitMode(str, Enum):
    fit = "fit"
    fill = "fill"
    stretch = "stretch"


class SourceBox(str, Enum):
    crop = "crop"
    media = "media"
    trim = "trim"
    bleed = "bleed"


class PaperPreset(BaseModel):
    name: str
    width: float
    height: float


class ImpositionSettings(BaseModel):
    job_id: str
    binding_mode: BindingMode = BindingMode.custom
    custom_signature_folios: str = "4"
    standard_signature_folios: int = Field(default=4, ge=1, le=16)
    flyleaf: bool | None = None
    flyleaf_arrangement: Literal["none", "single", "double"] = "double"
    front_flyleaf_leaves: int = Field(default=2, ge=0, le=8)
    back_flyleaf_leaves: int = Field(default=2, ge=0, le=8)
    paper: PaperPreset = Field(default_factory=lambda: PaperPreset(name="Letter", width=612, height=792))
    book_width: float | None = None
    book_height: float | None = None
    fit_mode: FitMode = FitMode.fit
    source_box: SourceBox = SourceBox.crop
    print_safe_margin: float = Field(default=14.2, ge=0, le=72)
    gutter: float = Field(default=0, ge=0, le=144)
    creep: float = Field(default=0, ge=0, le=72)
    duplex: bool = True
    flip_edge: Literal["short", "long"] = "short"
    book_type: Literal["custom", "practice", "general_hardcover", "trpg_reference", "deluxe_tome"] = "custom"
    sewing_layout: Literal["custom", "unsupported_3", "unsupported_5", "two_tape", "three_tape"] = "custom"
    split_output: Literal["combined", "by_signature"] = "by_signature"
    crop_marks: bool = False
    sewing_marks: bool = False
    sewing_debug_marks: bool = False
    sewing_station_count: int = Field(default=5, ge=2, le=12)
    sewing_station_margin: float = Field(default=56.6929133858, ge=0, le=216)
    sewing_mark_length: float = Field(default=11.3, ge=2, le=36)
    tape_supports: bool = True
    tape_count: int = Field(default=3, ge=0, le=6)
    tape_width: float = Field(default=17.0, ge=0, le=72)
    project_name: str | None = None
    fidelity: Literal["vector", "raster", "auto"] = "auto"
    raster_dpi: int = Field(default=600, ge=72, le=600)
    auto_validation_dpi: int = Field(default=150, ge=72, le=300)
    auto_diff_threshold: float = Field(default=3.0, ge=0, le=100)
    auto_diff_mode: Literal["rmse", "pixel"] = "rmse"
    manual_raster_pages: list[int] = Field(default_factory=list)
    manual_vector_pages: list[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_flyleaf_settings(cls, data):
        if not isinstance(data, dict):
            return data

        migrated = dict(data)
        has_new_flyleaf = any(key in migrated for key in ("flyleaf_arrangement", "front_flyleaf_leaves", "back_flyleaf_leaves"))
        if not has_new_flyleaf and "flyleaf" in migrated:
            if migrated.get("flyleaf"):
                migrated["flyleaf_arrangement"] = "single"
                migrated["front_flyleaf_leaves"] = 1
                migrated["back_flyleaf_leaves"] = 1
            else:
                migrated["flyleaf_arrangement"] = "none"
                migrated["front_flyleaf_leaves"] = 0
                migrated["back_flyleaf_leaves"] = 0
        elif "flyleaf_arrangement" in migrated:
            arrangement = migrated["flyleaf_arrangement"]
            defaults = {"none": 0, "single": 1, "double": 2}
            if arrangement in defaults:
                migrated.setdefault("front_flyleaf_leaves", defaults[arrangement])
                migrated.setdefault("back_flyleaf_leaves", defaults[arrangement])

        return migrated

    @model_validator(mode="after")
    def sync_flyleaf_bool(self):
        self.flyleaf = self.front_flyleaf_leaves > 0 or self.back_flyleaf_leaves > 0
        return self


class PageSlot(BaseModel):
    source_page: int | None
    label: str
    side: Literal["front", "back"]
    position: Literal["left", "right"]
    rect: tuple[float, float, float, float]
    rotation: int = 0
    is_blank: bool = False


class SheetPlan(BaseModel):
    index: int
    signature_index: int
    sheet_in_signature: int
    front: list[PageSlot]
    back: list[PageSlot]


class SignaturePlan(BaseModel):
    index: int
    folios: int
    pages: list[int | None]
    sheets: list[int]


class ImpositionPlan(BaseModel):
    job_id: str
    total_source_pages: int
    total_imposed_pages: int
    blank_pages: int
    flyleaf_pages: int = 0
    padding_blank_pages: int = 0
    signatures: list[SignaturePlan]
    sheets: list[SheetPlan]
    warnings: list[str] = []


class PdfPageInfo(BaseModel):
    index: int
    width: float
    height: float
    rotation: int
    boxes: dict[str, tuple[float, float, float, float] | None]


class PreflightItem(BaseModel):
    severity: Literal["ok", "info", "warning", "danger"]
    title: str
    detail: str
    recommendation: str


class PdfInspectResult(BaseModel):
    job_id: str
    filename: str
    path: str
    page_count: int
    pdf_version: str | None
    encrypted: bool
    pages: list[PdfPageInfo]
    warnings: list[str]
    preflight: list[PreflightItem] = []


class AutoFidelityDecision(BaseModel):
    source_page: int
    mode: Literal["vector", "raster"]
    reason: str
    diff_score: float | None = None
    threshold: float | None = None


class ExportReport(BaseModel):
    fidelity: Literal["vector", "raster", "auto"]
    total_slots: int
    vector_slots: int
    raster_slots: int
    auto_validated_pages: int = 0
    raster_fallback_pages: list[int] = Field(default_factory=list)
    manual_raster_pages: list[int] = Field(default_factory=list)
    manual_vector_pages: list[int] = Field(default_factory=list)
    decisions: list[AutoFidelityDecision] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExportResult(BaseModel):
    job_id: str
    output_paths: list[str]
    validation_warnings: list[str]
    plan: ImpositionPlan
    export_report: ExportReport | None = None


class PreviewRequest(BaseModel):
    settings: ImpositionSettings
    sheet_index: int = 0
    side: Literal["front", "back"] = "front"


class ContactSheetRequest(BaseModel):
    settings: ImpositionSettings


class CalibrationRequest(BaseModel):
    paper: PaperPreset = Field(default_factory=lambda: PaperPreset(name="Letter", width=612, height=792))
    print_safe_margin: float = Field(default=14.2, ge=0, le=72)
    flip_edge: Literal["short", "long"] = "short"


class SignatureRecommendationRequest(BaseModel):
    total_pages: int = Field(ge=0)
    flyleaf: bool | None = None
    flyleaf_arrangement: Literal["none", "single", "double"] = "double"
    front_flyleaf_leaves: int = Field(default=2, ge=0, le=8)
    back_flyleaf_leaves: int = Field(default=2, ge=0, le=8)
    preferred: int = Field(default=4, ge=1, le=16)
    max_folios: int = Field(default=5, ge=1, le=16)
    avoid_one: bool = True

    @model_validator(mode="before")
    @classmethod
    def migrate_flyleaf_settings(cls, data):
        return ImpositionSettings.migrate_flyleaf_settings(data)

    @model_validator(mode="after")
    def sync_flyleaf_bool(self):
        self.flyleaf = self.front_flyleaf_leaves > 0 or self.back_flyleaf_leaves > 0
        return self


class SignatureRecommendationResult(BaseModel):
    total_pages: int
    total_sheets: int
    folios: list[int]


class PunchingTemplateRequest(BaseModel):
    settings: ImpositionSettings


class SewingStation(BaseModel):
    index: int
    y_pt: float
    y_mm: float


class PunchingTemplateInfo(BaseModel):
    width_pt: float
    height_pt: float
    width_mm: float
    height_mm: float
    folded_signature_height_pt: float
    folded_signature_height_mm: float
    station_positions: list[SewingStation]
