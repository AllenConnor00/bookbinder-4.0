from backend.bookbinder4.binding import build_plan, parse_custom_folios
from backend.bookbinder4.models import BindingMode, ImpositionSettings


def test_parse_custom_folios_accepts_friendly_input():
    assert parse_custom_folios("4, 4, 3") == [4, 4, 3]
    assert parse_custom_folios("folios: 2 / 6") == [2, 6]


def test_single_folio_signature_order():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1")
    plan = build_plan(4, settings)
    assert plan.blank_pages == 0
    assert len(plan.sheets) == 1
    assert [slot.source_page for slot in plan.sheets[0].front] == [4, 1]
    assert [slot.source_page for slot in plan.sheets[0].back] == [2, 3]


def test_two_folio_signature_order():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2")
    plan = build_plan(8, settings)
    assert len(plan.sheets) == 2
    assert [slot.source_page for slot in plan.sheets[0].front] == [8, 1]
    assert [slot.source_page for slot in plan.sheets[0].back] == [2, 7]
    assert [slot.source_page for slot in plan.sheets[1].front] == [6, 3]
    assert [slot.source_page for slot in plan.sheets[1].back] == [4, 5]


def test_padding_blanks_to_multiple_of_four():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1")
    plan = build_plan(5, settings)
    assert plan.total_imposed_pages == 8
    assert plan.blank_pages == 3
    seen = [page for sig in plan.signatures for page in sig.pages if page is not None]
    assert seen == [1, 2, 3, 4, 5]


def test_custom_signature_repeats_last_size_when_short():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2")
    plan = build_plan(20, settings)
    assert [sig.folios for sig in plan.signatures] == [2, 2, 2]
    assert plan.blank_pages == 4
    assert any("repeated" in warning for warning in plan.warnings)


def test_perfect_bound_groups_consecutive_pages():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.perfect_bound)
    plan = build_plan(8, settings)
    assert len(plan.signatures) == 2
    assert [slot.source_page for slot in plan.sheets[0].front] == [4, 1]
    assert [slot.source_page for slot in plan.sheets[0].back] == [2, 3]
    assert [slot.source_page for slot in plan.sheets[1].front] == [8, 5]


def test_creep_moves_outer_sheet_pages_away_from_fold():
    base = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2", creep=0, print_safe_margin=14.2)
    creep = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2", creep=6, print_safe_margin=14.2)
    base_plan = build_plan(8, base)
    creep_plan = build_plan(8, creep)
    assert creep_plan.sheets[0].front[0].rect[0] == base_plan.sheets[0].front[0].rect[0]
    assert creep_plan.sheets[0].front[0].rect[2] < base_plan.sheets[0].front[0].rect[2]
    assert creep_plan.sheets[0].front[1].rect[0] > base_plan.sheets[0].front[1].rect[0]
    assert creep_plan.sheets[1].front[0].rect == base_plan.sheets[1].front[0].rect


def test_print_safe_margin_bounds_page_slots():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1", print_safe_margin=18)
    plan = build_plan(4, settings)
    sheet_w = max(settings.paper.width, settings.paper.height)
    sheet_h = min(settings.paper.width, settings.paper.height)
    for slot in plan.sheets[0].front + plan.sheets[0].back:
        assert slot.rect[0] >= 18
        assert slot.rect[1] >= 18
        assert slot.rect[2] <= sheet_w - 18
        assert slot.rect[3] <= sheet_h - 18
