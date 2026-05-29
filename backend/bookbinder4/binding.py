from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .models import BindingMode, ImpositionPlan, ImpositionSettings, PageSlot, SheetPlan, SignaturePlan


@dataclass(frozen=True)
class SlotDef:
    source_page: int | None
    side: str
    position: str


def parse_custom_folios(value: str) -> list[int]:
    folios = [int(match) for match in re.findall(r"\d+", value or "")]
    return [folio for folio in folios if folio > 0]


def page_sequence(page_count: int, flyleaf: bool) -> list[int | None]:
    pages: list[int | None] = list(range(1, page_count + 1))
    if flyleaf:
        pages = [None, None] + pages + [None, None]
    while len(pages) % 4:
        pages.append(None)
    return pages


def standard_folios(total_pages: int, target_folios: int) -> list[int]:
    sheets = math.ceil(total_pages / 4)
    folios: list[int] = []
    remaining = sheets
    while remaining > 0:
        folio_count = min(target_folios, remaining)
        folios.append(folio_count)
        remaining -= folio_count
    return folios


def folios_for_settings(settings: ImpositionSettings, total_pages: int) -> tuple[list[int], list[str]]:
    warnings: list[str] = []
    sheets = math.ceil(total_pages / 4)

    if settings.binding_mode == BindingMode.booklet:
        return [sheets], warnings
    if settings.binding_mode == BindingMode.perfect_bound:
        return [1] * sheets, warnings
    if settings.binding_mode == BindingMode.standard:
        return standard_folios(total_pages, settings.standard_signature_folios), warnings

    folios = parse_custom_folios(settings.custom_signature_folios)
    if not folios:
        folios = [settings.standard_signature_folios]
        warnings.append("Custom signatures were empty, so the standard folio count was used.")

    capacity = sum(f * 4 for f in folios)
    if capacity < total_pages:
        repeat = folios[-1]
        while capacity < total_pages:
            folios.append(repeat)
            capacity += repeat * 4
        warnings.append("Custom signatures did not cover the whole book, so the last folio size was repeated.")
    return folios, warnings


def split_signatures(pages: list[int | None], folios: list[int]) -> list[list[int | None]]:
    signatures: list[list[int | None]] = []
    cursor = 0
    for folio in folios:
        capacity = folio * 4
        chunk = pages[cursor : cursor + capacity]
        if not chunk:
            break
        while len(chunk) < capacity:
            chunk.append(None)
        signatures.append(chunk)
        cursor += capacity
    if cursor < len(pages):
        extra = pages[cursor:]
        while len(extra) % 4:
            extra.append(None)
        signatures.append(extra)
    return signatures


def booklet_slots(signature_pages: list[int | None]) -> list[tuple[list[SlotDef], list[SlotDef]]]:
    slots: list[tuple[list[SlotDef], list[SlotDef]]] = []
    left = 0
    right = len(signature_pages) - 1
    while left < right:
        front = [
            SlotDef(signature_pages[right], "front", "left"),
            SlotDef(signature_pages[left], "front", "right"),
        ]
        back = [
            SlotDef(signature_pages[left + 1], "back", "left"),
            SlotDef(signature_pages[right - 1], "back", "right"),
        ]
        slots.append((front, back))
        left += 2
        right -= 2
    return slots


def perfect_bound_slots(signature_pages: list[int | None]) -> list[tuple[list[SlotDef], list[SlotDef]]]:
    slots: list[tuple[list[SlotDef], list[SlotDef]]] = []
    for i in range(0, len(signature_pages), 4):
        group = signature_pages[i : i + 4]
        while len(group) < 4:
            group.append(None)
        slots.append(
            (
                [SlotDef(group[3], "front", "left"), SlotDef(group[0], "front", "right")],
                [SlotDef(group[1], "back", "left"), SlotDef(group[2], "back", "right")],
            )
        )
    return slots


def slot_rects(settings: ImpositionSettings, folios: int, sheet_in_signature: int) -> dict[str, tuple[float, float, float, float]]:
    sheet_w = max(settings.paper.width, settings.paper.height)
    sheet_h = min(settings.paper.width, settings.paper.height)
    gutter = settings.gutter
    margin = settings.print_safe_margin
    half = sheet_w / 2
    max_depth = max(0, folios - 1)
    creep_offset = settings.creep * max(0, max_depth - sheet_in_signature)
    left_rect = (margin, margin, half - gutter / 2 - creep_offset, sheet_h - margin)
    right_rect = (half + gutter / 2 + creep_offset, margin, sheet_w - margin, sheet_h - margin)
    return {
        "left": left_rect,
        "right": right_rect,
    }


def build_plan(page_count: int, settings: ImpositionSettings) -> ImpositionPlan:
    warnings: list[str] = []
    pages = page_sequence(page_count, settings.flyleaf)
    folios, folio_warnings = folios_for_settings(settings, len(pages))
    warnings.extend(folio_warnings)
    signatures = split_signatures(pages, folios)
    sheet_plans: list[SheetPlan] = []
    signature_plans: list[SignaturePlan] = []

    for sig_index, sig_pages in enumerate(signatures):
        sig_sheet_indices: list[int] = []
        pairs = (
            perfect_bound_slots(sig_pages)
            if settings.binding_mode == BindingMode.perfect_bound
            else booklet_slots(sig_pages)
        )
        for sheet_in_sig, (front_defs, back_defs) in enumerate(pairs):
            sheet_index = len(sheet_plans)
            sig_sheet_indices.append(sheet_index)
            rects = slot_rects(settings, max(1, len(sig_pages) // 4), sheet_in_sig)
            front = [_page_slot(defn, rects[defn.position]) for defn in front_defs]
            back = [_page_slot(defn, rects[defn.position]) for defn in back_defs]
            sheet_plans.append(
                SheetPlan(
                    index=sheet_index,
                    signature_index=sig_index,
                    sheet_in_signature=sheet_in_sig,
                    front=front,
                    back=back,
                )
            )
        signature_plans.append(
            SignaturePlan(
                index=sig_index,
                folios=max(1, len(sig_pages) // 4),
                pages=sig_pages,
                sheets=sig_sheet_indices,
            )
        )

    blank_pages = sum(1 for sig in signatures for page in sig if page is None)
    if blank_pages:
        warnings.append(f"{blank_pages} blank page(s) will be added to complete the signatures.")

    return ImpositionPlan(
        job_id=settings.job_id,
        total_source_pages=page_count,
        total_imposed_pages=sum(len(sig) for sig in signatures),
        blank_pages=blank_pages,
        signatures=signature_plans,
        sheets=sheet_plans,
        warnings=warnings,
    )


def _page_slot(defn: SlotDef, rect: tuple[float, float, float, float]) -> PageSlot:
    return PageSlot(
        source_page=defn.source_page,
        label="Blank" if defn.source_page is None else str(defn.source_page),
        side=defn.side,  # type: ignore[arg-type]
        position=defn.position,  # type: ignore[arg-type]
        rect=rect,
        is_blank=defn.source_page is None,
    )
