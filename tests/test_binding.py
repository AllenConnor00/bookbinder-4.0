from backend.bookbinder4.binding import build_plan, parse_custom_folios, recommend_folios
from backend.bookbinder4.models import BindingMode, ImpositionSettings


def no_flyleaf_settings(**kwargs):
    return ImpositionSettings(flyleaf_arrangement="none", front_flyleaf_leaves=0, back_flyleaf_leaves=0, **kwargs)


def test_parse_custom_folios_accepts_friendly_input():
    assert parse_custom_folios("4, 4, 3") == [4, 4, 3]
    assert parse_custom_folios("folios: 2 / 6") == [2, 6]


def test_recommend_folios_prefers_four_sheet_signatures():
    assert recommend_folios(32) == [4, 4]
    assert recommend_folios(36) in ([5, 4], [4, 5])
    assert recommend_folios(48) == [4, 4, 4]


def test_recommend_folios_avoids_final_one_when_practical():
    assert recommend_folios(52) == [5, 4, 4]
    assert recommend_folios(68) == [5, 4, 4, 4]
    assert 1 not in recommend_folios(40)
    assert recommend_folios(4) == [1]


def test_recommend_folios_expected_edge_cases():
    assert recommend_folios(40) in ([5, 5], [4, 4, 2])
    assert recommend_folios(44) in ([4, 4, 3], [5, 4, 2])


def test_standard_four_folios_uses_recommendation():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.standard, standard_signature_folios=4)
    plan = build_plan(52, settings)
    assert [sig.folios for sig in plan.signatures] == [5, 4, 4]


def test_single_folio_signature_order():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1")
    plan = build_plan(4, settings)
    assert plan.blank_pages == 0
    assert len(plan.sheets) == 1
    assert [slot.source_page for slot in plan.sheets[0].front] == [4, 1]
    assert [slot.source_page for slot in plan.sheets[0].back] == [2, 3]


def test_two_folio_signature_order():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2")
    plan = build_plan(8, settings)
    assert len(plan.sheets) == 2
    assert [slot.source_page for slot in plan.sheets[0].front] == [8, 1]
    assert [slot.source_page for slot in plan.sheets[0].back] == [2, 7]
    assert [slot.source_page for slot in plan.sheets[1].front] == [6, 3]
    assert [slot.source_page for slot in plan.sheets[1].back] == [4, 5]


def test_padding_blanks_to_multiple_of_four():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1")
    plan = build_plan(5, settings)
    assert plan.total_imposed_pages == 8
    assert plan.blank_pages == 3
    seen = [page for sig in plan.signatures for page in sig.pages if page is not None]
    assert seen == [1, 2, 3, 4, 5]


def test_custom_signature_repeats_last_size_when_short():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2")
    plan = build_plan(20, settings)
    assert [sig.folios for sig in plan.signatures] == [2, 2, 2]
    assert plan.blank_pages == 4
    assert any("repeated" in warning for warning in plan.warnings)


def test_perfect_bound_groups_consecutive_pages():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.perfect_bound)
    plan = build_plan(8, settings)
    assert len(plan.signatures) == 2
    assert [slot.source_page for slot in plan.sheets[0].front] == [4, 1]
    assert [slot.source_page for slot in plan.sheets[0].back] == [2, 3]
    assert [slot.source_page for slot in plan.sheets[1].front] == [8, 5]


def test_creep_moves_outer_sheet_pages_away_from_fold():
    base = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2", creep=0, print_safe_margin=14.2)
    creep = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="2", creep=6, print_safe_margin=14.2)
    base_plan = build_plan(8, base)
    creep_plan = build_plan(8, creep)
    assert creep_plan.sheets[0].front[0].rect[0] == base_plan.sheets[0].front[0].rect[0]
    assert creep_plan.sheets[0].front[0].rect[2] < base_plan.sheets[0].front[0].rect[2]
    assert creep_plan.sheets[0].front[1].rect[0] > base_plan.sheets[0].front[1].rect[0]
    assert creep_plan.sheets[1].front[0].rect == base_plan.sheets[1].front[0].rect


def test_print_safe_margin_bounds_page_slots():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1", print_safe_margin=18)
    plan = build_plan(4, settings)
    sheet_w = max(settings.paper.width, settings.paper.height)
    sheet_h = min(settings.paper.width, settings.paper.height)
    for slot in plan.sheets[0].front + plan.sheets[0].back:
        assert slot.rect[0] >= 18
        assert slot.rect[1] >= 18
        assert slot.rect[2] <= sheet_w - 18
        assert slot.rect[3] <= sheet_h - 18


def test_no_flyleaf_adds_only_padding_blanks():
    settings = no_flyleaf_settings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="1")
    plan = build_plan(5, settings)
    assert plan.flyleaf_pages == 0
    assert plan.padding_blank_pages == 3
    assert plan.blank_pages == 3
    assert plan.total_imposed_pages == 8


def test_single_flyleaf_adds_one_leaf_front_and_back():
    settings = ImpositionSettings(job_id="test", flyleaf_arrangement="single", front_flyleaf_leaves=1, back_flyleaf_leaves=1, binding_mode=BindingMode.custom, custom_signature_folios="2")
    plan = build_plan(4, settings)
    assert plan.flyleaf_pages == 4
    assert plan.padding_blank_pages == 0
    assert plan.blank_pages == 4
    assert plan.signatures[0].pages == [None, None, 1, 2, 3, 4, None, None]


def test_double_flyleaf_is_default_for_hardcover_workflow():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.custom, custom_signature_folios="3")
    plan = build_plan(4, settings)
    assert settings.front_flyleaf_leaves == 2
    assert settings.back_flyleaf_leaves == 2
    assert plan.flyleaf_pages == 8
    assert plan.padding_blank_pages == 0
    assert plan.blank_pages == 8
    assert plan.total_imposed_pages == 12
    assert plan.signatures[0].pages == [None, None, None, None, 1, 2, 3, 4, None, None, None, None]


def test_front_only_and_back_only_flyleaves_are_supported():
    front_only = ImpositionSettings(job_id="front", flyleaf_arrangement="none", front_flyleaf_leaves=1, back_flyleaf_leaves=0, binding_mode=BindingMode.custom, custom_signature_folios="2")
    back_only = ImpositionSettings(job_id="back", flyleaf_arrangement="none", front_flyleaf_leaves=0, back_flyleaf_leaves=1, binding_mode=BindingMode.custom, custom_signature_folios="2")
    assert build_plan(4, front_only).signatures[0].pages[:2] == [None, None]
    assert build_plan(4, back_only).signatures[0].pages[4:6] == [None, None]


def test_padding_happens_after_flyleaf_insertion():
    settings = ImpositionSettings(job_id="test", flyleaf_arrangement="single", front_flyleaf_leaves=1, back_flyleaf_leaves=1, binding_mode=BindingMode.custom, custom_signature_folios="3")
    plan = build_plan(5, settings)
    assert plan.flyleaf_pages == 4
    assert plan.padding_blank_pages == 3
    assert plan.blank_pages == 7
    assert plan.total_imposed_pages == 12


def test_double_flyleaf_signature_splitting_uses_augmented_page_count():
    settings = ImpositionSettings(job_id="test", binding_mode=BindingMode.standard, standard_signature_folios=4)
    plan = build_plan(52, settings)
    assert plan.flyleaf_pages == 8
    assert plan.total_imposed_pages == 60
    assert [signature.folios for signature in plan.signatures] == [4, 4, 4, 3]
    assert 1 not in [signature.folios for signature in plan.signatures]


def test_old_boolean_flyleaf_settings_still_load():
    old_single = ImpositionSettings(job_id="old", flyleaf=True)
    old_none = ImpositionSettings(job_id="old", flyleaf=False)
    assert old_single.flyleaf_arrangement == "single"
    assert old_single.front_flyleaf_leaves == 1
    assert old_single.back_flyleaf_leaves == 1
    assert old_none.flyleaf_arrangement == "none"
    assert old_none.front_flyleaf_leaves == 0
    assert old_none.back_flyleaf_leaves == 0
