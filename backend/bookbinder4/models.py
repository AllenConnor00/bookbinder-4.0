from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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
    flyleaf: bool = False
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
    split_output: Literal["combined", "by_signature"] = "by_signature"
    crop_marks: bool = False
    sewing_marks: bool = False
    sewing_station_count: int = Field(default=5, ge=2, le=12)
    sewing_station_margin: float = Field(default=56.7, ge=0, le=216)
    sewing_mark_length: float = Field(default=11.3, ge=2, le=36)
    fidelity: Literal["hybrid", "vector", "raster"] = "raster"
    raster_dpi: int = Field(default=300, ge=72, le=600)


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


class ExportResult(BaseModel):
    job_id: str
    output_paths: list[str]
    validation_warnings: list[str]
    plan: ImpositionPlan


class PreviewRequest(BaseModel):
    settings: ImpositionSettings
    sheet_index: int = 0
    side: Literal["front", "back"] = "front"


class ContactSheetRequest(BaseModel):
    settings: ImpositionSettings


class CalibrationRequest(BaseModel):
    paper: PaperPreset = Field(default_factory=lambda: PaperPreset(name="Letter", width=612, height=792))
    print_safe_margin: float = Field(default=14.2, ge=0, le=72)
