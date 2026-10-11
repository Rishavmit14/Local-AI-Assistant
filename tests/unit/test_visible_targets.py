from datetime import UTC, datetime

import pytest

from local_ai_assistant.desktop.agency import ElementIdentity
from local_ai_assistant.desktop.agency_ledger import ComputerAgencyLedger
from local_ai_assistant.desktop.observation import AccessibleElement, DesktopObservation
from local_ai_assistant.desktop.visible_targets import (
    VisibleTargetAmbiguous,
    VisibleTargetOrderUnavailable,
    parse_visible_target_clarification,
    parse_visible_target_intent,
    rebind_visible_target,
    resolve_visible_target,
)
from local_ai_assistant.perception.screen import ScreenLabelLocation

APP = "org.gnome.Nautilus"
WINDOW_PATH = (0, 0)
COLLECTION_PATH = (*WINDOW_PATH, 1)


def _files_observation(names=("Cedar", "Amber", "Birch"), *, selected=(), complete=True,
                       observation_id="observation_current", frame_name="qualification-probe-4",
                       collection_path=COLLECTION_PATH):
    elements = [AccessibleElement(
        WINDOW_PATH, APP, "frame", frame_name, (0, 0, 900, 700), (), True,
    ), AccessibleElement(
        collection_path, APP, "tree table", "Content View", (0, 0, 700, 500), (), False,
    )]
    for index, name in enumerate(names):
        row_path = (*collection_path, index)
        elements.extend((
            AccessibleElement(
                row_path, APP, "tree item", name, (0, 0, 662, 44), (), False,
                selected=name in selected, collection_path=collection_path,
                collection_role="tree table", collection_name="Content View",
                item_path=row_path,
            ),
            AccessibleElement(
                (*row_path, 0), APP, "label", name, (0, 0, 442, 44), ("link.open",), False,
                collection_path=collection_path, collection_role="tree table",
                collection_name="Content View",
            ),
        ))
    canonical = "|".join(f"{item.path}:{item.name}:{item.selected}" for item in elements)
    return DesktopObservation(
        observation_id, datetime.now(UTC).isoformat(), canonical,
        tuple(elements), complete=complete,
    )


def _visual_order():
    return {
        "Amber": ScreenLabelLocation("Amber", (840, 430, 120, 32), 95.0),
        "Birch": ScreenLabelLocation("Birch", (840, 480, 120, 32), 96.0),
        "Cedar": ScreenLabelLocation("Cedar", (840, 530, 120, 32), 94.0),
    }


@pytest.mark.parametrize(("utterance", "ordinal", "last", "selected"), [
    ("Open the first folder", 1, False, False),
    ("Open the second folder in this Files window.", 2, False, False),
    ("Open the third visible directory", 3, False, False),
    ("Open the last folder", None, True, False),
    ("Open the selected folder", None, False, True),
    ("Open the 2nd folder", 2, False, False),
    ("Open the 2 folder", 2, False, False),
])
def test_visible_target_intent_parses_general_folder_references(utterance, ordinal, last, selected):
    intent = parse_visible_target_intent(utterance)
    assert intent is not None
    assert (intent.ordinal, intent.last, intent.selected) == (ordinal, last, selected)


@pytest.mark.parametrize("utterance", [
    "Open the eleventh folder", "Open the second folder and then delete it",
    "Open the folder named Birch",
])
def test_visible_target_intent_rejects_out_of_scope_or_chained_requests(utterance):
    assert parse_visible_target_intent(utterance) is None


def test_historical_asr_transcript_keeps_raw_text_and_extracts_only_groundable_ordinal():
    transcript = "Open the second folder in this files video."
    intent = parse_visible_target_intent(transcript)

    assert intent is not None
    assert (intent.verb, intent.kind, intent.ordinal) == ("open", "folder", 2)
    assert transcript.endswith("files video.")
    assert parse_visible_target_intent("Open the second folder in this window.").ordinal == 2


def test_exact_historical_transcript_read_only_replay_binds_second_visible_folder(tmp_path):
    transcript = "Open the second folder in this files video."
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    task = ledger.create("owner", transcript)
    observation = _files_observation(names=("Amber", "Birch", "Cedar"))
    intent = parse_visible_target_intent(task.request)

    assert task.request == transcript
    binding = resolve_visible_target(
        observation, intent,
        folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
    )

    assert (binding.label, binding.ordinal, binding.order_method) == (
        "Birch", 2, "local-ocr-geometry",
    )
    assert ledger.task(task.task_id).action_count == 0
    assert ledger.recent_actions(task.task_id) == ()


def test_visible_target_clarification_can_restate_reference_but_rejects_ambiguous_text():
    original = "Open the second folder in this Files window."

    clarified = parse_visible_target_clarification(original, "Yes, the third one.")

    assert clarified is not None
    assert (clarified.verb, clarified.kind, clarified.ordinal) == ("open", "folder", 3)
    assert parse_visible_target_clarification(original, "Use the video") is None


def test_ordinal_uses_current_visual_geometry_not_traversal_or_filesystem_order():
    observation = _files_observation()
    intent = parse_visible_target_intent("Open the second folder in this Files window.")

    binding = resolve_visible_target(
        observation, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
    )

    assert binding.label == "Birch"
    assert binding.ordinal == 2
    assert binding.order_method == "local-ocr-geometry"
    assert binding.target == ElementIdentity((*COLLECTION_PATH, 2, 0), APP, "label", "Birch")


def test_stale_collection_rebind_preserves_same_ordinal_item_after_trailing_addition():
    intent = parse_visible_target_intent("Open the second folder")
    old_state = _files_observation(
        names=("Amber", "Birch", "Cedar"), observation_id="observation_" + "a" * 32,
    )
    old = resolve_visible_target(
        old_state, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
    )
    new_state = _files_observation(
        names=("Amber", "Birch", "Cedar", "Zephyr"), observation_id="observation_" + "b" * 32,
    )
    locations = {
        **_visual_order(),
        "Zephyr": ScreenLabelLocation("Zephyr", (840, 580, 120, 32), 94.0),
    }

    rebound = rebind_visible_target(
        old, new_state, intent,
        folder_names=frozenset({"Amber", "Birch", "Cedar", "Zephyr"}),
        ocr_locations=locations, expected_applications=frozenset({APP}),
    )

    assert rebound.label == "Birch"
    assert rebound.ordinal == old.ordinal == 2
    assert rebound.collection_size == 4
    assert rebound.observation_id == new_state.observation_id
    assert rebound.collection_digest != old.collection_digest


def test_stale_ordinal_rebind_refuses_changed_referent_and_wrong_window():
    intent = parse_visible_target_intent("Open the second folder")
    old_state = _files_observation(
        names=("Amber", "Birch", "Cedar"), observation_id="observation_" + "a" * 32,
    )
    old = resolve_visible_target(
        old_state, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
    )
    changed = _files_observation(
        names=("Amber", "Aster", "Birch", "Cedar"), observation_id="observation_" + "c" * 32,
    )
    locations = {
        "Amber": ScreenLabelLocation("Amber", (840, 430, 120, 32), 95.0),
        "Aster": ScreenLabelLocation("Aster", (840, 455, 120, 32), 95.0),
        "Birch": ScreenLabelLocation("Birch", (840, 480, 120, 32), 96.0),
        "Cedar": ScreenLabelLocation("Cedar", (840, 530, 120, 32), 94.0),
    }
    with pytest.raises(VisibleTargetAmbiguous, match="can't confirm the same item"):
        rebind_visible_target(
            old, changed, intent,
            folder_names=frozenset({"Amber", "Aster", "Birch", "Cedar"}),
            ocr_locations=locations, expected_applications=frozenset({APP}),
        )

    different_window = _files_observation(
        names=("Amber", "Birch", "Cedar"), observation_id="observation_" + "d" * 32,
        frame_name="Different Files window",
    )
    with pytest.raises(VisibleTargetAmbiguous, match="can't confirm the same item"):
        rebind_visible_target(
            old, different_window, intent,
            folder_names=frozenset({"Amber", "Birch", "Cedar"}),
            ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
        )


def test_stale_rebind_refuses_when_bound_folder_disappears():
    intent = parse_visible_target_intent("Open the second folder")
    original = _files_observation(
        names=("Amber", "Birch", "Cedar"),
        observation_id="observation_" + "a" * 32,
    )
    binding = resolve_visible_target(
        original, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
    )
    changed = _files_observation(
        names=("Amber", "Cedar"),
        observation_id="observation_" + "b" * 32,
    )
    changed_order = {
        "Amber": ScreenLabelLocation("Amber", (840, 430, 120, 32), 95.0),
        "Cedar": ScreenLabelLocation("Cedar", (840, 480, 120, 32), 95.0),
    }

    with pytest.raises(VisibleTargetAmbiguous, match="can't confirm the same item"):
        rebind_visible_target(
            binding, changed, intent,
            folder_names=frozenset({"Amber", "Cedar"}),
            ocr_locations=changed_order, expected_applications=frozenset({APP}),
        )


def test_stale_rebind_contract_also_handles_browser_search_results():
    app = "Google Chrome"
    frame_path, list_path = (0,), (0, 1)

    def browser_observation(names, marker):
        elements = [
            AccessibleElement(frame_path, app, "frame", "Search - query", (0, 0, 900, 700), (), True),
            AccessibleElement(list_path, app, "list", "Search results", (0, 80, 800, 500), (), False),
        ]
        for index, name in enumerate(names):
            path = (*list_path, index)
            elements.append(AccessibleElement(
                path, app, "link", name, (0, 100 + index * 40, 700, 32), ("jump",), False,
                collection_path=list_path, collection_role="list", collection_name="Search results",
                item_path=path,
            ))
        return DesktopObservation(
            "observation_" + marker * 32, datetime.now(UTC).isoformat(), marker * 64,
            tuple(elements),
        )

    intent = parse_visible_target_intent("Open the second result")
    before = browser_observation(("Result A", "Result B"), "e")
    binding = resolve_visible_target(before, intent)
    after = browser_observation(("Result A", "Result B", "Result C"), "f")

    rebound = rebind_visible_target(binding, after, intent)

    assert rebound.label == "Result B"
    assert rebound.ordinal == 2
    assert rebound.collection_size == 3


def test_visible_target_refuses_same_label_and_ordinal_in_a_different_collection():
    intent = parse_visible_target_intent("Open the second folder")
    original = _files_observation(
        names=("Amber", "Birch", "Cedar"),
        observation_id="observation_" + "1" * 32,
    )
    moved_container = _files_observation(
        names=("Amber", "Birch", "Cedar"),
        observation_id="observation_" + "2" * 32,
        collection_path=(0, 0, 4),
    )
    binding = resolve_visible_target(
        original, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
    )

    with pytest.raises(VisibleTargetAmbiguous, match="can't confirm the same item"):
        rebind_visible_target(
            binding, moved_container, intent,
            folder_names=frozenset({"Amber", "Birch", "Cedar"}),
            ocr_locations=_visual_order(), expected_applications=frozenset({APP}),
        )


def test_visible_target_fails_closed_when_order_is_not_available():
    observation = _files_observation()
    intent = parse_visible_target_intent("Open the second folder")

    with pytest.raises(VisibleTargetOrderUnavailable):
        resolve_visible_target(
            observation, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        )


def test_selected_target_uses_the_unique_current_selection_without_geometry():
    observation = _files_observation(selected={"Birch"})
    intent = parse_visible_target_intent("Open the selected folder")

    binding = resolve_visible_target(
        observation, intent, folder_names=frozenset({"Amber", "Birch", "Cedar"}),
    )

    assert binding.label == "Birch"
    assert binding.order_method == "current-selection"


def test_multiple_selections_and_incomplete_observations_require_clarification():
    intent = parse_visible_target_intent("Open the selected folder")
    with pytest.raises(VisibleTargetAmbiguous, match="More than one item is selected"):
        resolve_visible_target(
            _files_observation(selected={"Amber", "Birch"}), intent,
            folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        )
    with pytest.raises(VisibleTargetAmbiguous, match="whole current collection"):
        resolve_visible_target(
            _files_observation(complete=False), intent,
            folder_names=frozenset({"Amber", "Birch", "Cedar"}),
        )


def test_visible_target_rejects_wrong_active_application_and_duplicate_labels():
    intent = parse_visible_target_intent("Open the second folder")
    with pytest.raises(VisibleTargetAmbiguous, match="isn't the Files window"):
        resolve_visible_target(
            _files_observation(), intent,
            folder_names=frozenset({"Amber", "Birch", "Cedar"}),
            expected_applications=frozenset({"OtherApp"}),
        )
    duplicated = _files_observation(names=("Amber", "Amber", "Cedar"))
    with pytest.raises(VisibleTargetAmbiguous, match="duplicate labels"):
        resolve_visible_target(
            duplicated, intent, folder_names=frozenset({"Amber", "Cedar"}),
            ocr_locations=_visual_order(),
        )
