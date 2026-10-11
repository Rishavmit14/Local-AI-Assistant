"""Resolve natural visible references to current AT-SPI targets without trusting labels."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from local_ai_assistant.perception.screen import ScreenLabelLocation

from .agency import ElementIdentity
from .observation import AccessibleElement, DesktopObservation

_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
_ITEM_KINDS = frozenset({
    "folder", "directory", "file", "item", "entry", "row", "button", "link",
    "result", "control",
})
_INTENT = re.compile(
    r"^\s*(?:(?:hey\s+)?friday[,:\s]+)?(?:please\s+)?"
    r"(?P<verb>open|click|select|activate)\s+(?:the\s+)?"
    r"(?P<reference>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|"
    r"selected|highlighted|\d{1,2}(?:st|nd|rd|th)?)\s+"
    r"(?:visible\s+)?(?P<kind>folder|directory|file|item|entry|row|button|link|result|control)"
    r"(?P<tail>\s+(?:in|on|within|from)\s+.+?)?[.!?]*\s*$",
    re.IGNORECASE,
)
_SELECTED_PHRASE = re.compile(
    r"^\s*(?:(?:hey\s+)?friday[,:\s]+)?(?:please\s+)?"
    r"(?P<verb>open|click|select|activate)\s+(?:the\s+)?"
    r"(?:one\s+i\s+selected|one\s+selected|selected\s+item|highlighted\s+item)"
    r"(?:\s+(?:in|on|within)\s+.+?)?[.!?]*\s*$",
    re.IGNORECASE,
)
_DEICTIC = re.compile(
    r"^\s*(?:(?:hey\s+)?friday[,:\s]+)?(?:please\s+)?"
    r"(?P<verb>open|click|select|activate)\s+(?:that|this|it)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_CLARIFICATION_REFERENCE = re.compile(
    r"^\s*(?:yes|yeah|correct|right|please|use|open|choose|select)?[,\s:]*"
    r"(?:the\s+)?(?P<reference>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"last|selected|highlighted|\d{1,2}(?:st|nd|rd|th)?)"
    r"(?:\s+(?:visible\s+)?(?P<kind>folder|directory|item|one))?[.!?]*\s*$",
    re.IGNORECASE,
)
_UNSUPPORTED_CHAIN = re.compile(r"[;\n]|\b(?:then|after|before|and then|delete|submit|send|buy|purchase)\b", re.I)
_FRAME_ROLES = {"frame", "window", "dialog", "alert"}
_COLLECTION_ROLES = {"list", "list box", "table", "tree", "tree table", "grid", "icon view"}
_FOLDER_ROLES = {"label", "table cell", "list item", "tree item", "icon", "link"}
_ACTIONS = {"click", "press", "activate", "jump", "link.open", "default.activate"}


@dataclass(frozen=True, slots=True)
class VisibleTargetIntent:
    verb: str
    kind: str
    ordinal: int | None = None
    last: bool = False
    selected: bool = False
    deictic: bool = False

    @property
    def plan_target(self) -> str:
        reference = "last" if self.last else "selected" if self.selected else (
            "deictic" if self.deictic else str(self.ordinal)
        )
        return f"{reference}:{self.kind}"


@dataclass(frozen=True, slots=True)
class VisibleTargetBinding:
    target: ElementIdentity
    expected_window: ElementIdentity
    label: str
    collection_path: tuple[int, ...]
    collection_role: str
    collection_name: str
    ordinal: int
    collection_size: int
    order_method: str
    collection_digest: str
    observation_id: str


class VisibleTargetAmbiguous(ValueError):
    """The current screen does not support a safe single referent."""


class VisibleTargetOrderUnavailable(VisibleTargetAmbiguous):
    """Semantic bounds do not establish order, so local OCR may supply geometry."""

    def __init__(self, message: str, *, labels: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.labels = labels


def parse_visible_target_intent(text: str) -> VisibleTargetIntent | None:
    """Parse a bounded ordinal/deictic grammar, not an app-specific workflow."""
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 512 or _UNSUPPORTED_CHAIN.search(text):
        return None
    match = _INTENT.fullmatch(text)
    if match:
        reference = match.group("reference").casefold()
        kind = match.group("kind").casefold()
        ordinal = _ORDINALS.get(reference)
        if ordinal is None and reference.isdigit():
            ordinal = int(reference)
        elif ordinal is None and reference[:-2].isdigit():
            ordinal = int(reference[:-2])
        if ordinal is not None and not 1 <= ordinal <= 10:
            return None
        if ordinal is None and reference not in {"last", "selected", "highlighted"}:
            return None
        return VisibleTargetIntent(
            match.group("verb").casefold(), kind, ordinal=ordinal,
            last=reference == "last", selected=reference in {"selected", "highlighted"},
        )
    selected = _SELECTED_PHRASE.fullmatch(text)
    if selected:
        return VisibleTargetIntent(selected.group("verb").casefold(), "item", selected=True)
    deictic = _DEICTIC.fullmatch(text)
    if deictic:
        return VisibleTargetIntent(deictic.group("verb").casefold(), "item", deictic=True)
    return None


def parse_visible_target_clarification(
    original_request: str, response: str,
) -> VisibleTargetIntent | None:
    """Resolve a concise answer against the original visible-item objective."""
    original = parse_visible_target_intent(original_request)
    if (original is None or not 1 <= len(response.strip()) <= 256
            or _UNSUPPORTED_CHAIN.search(response)):
        return None
    match = _CLARIFICATION_REFERENCE.fullmatch(response)
    if match is None:
        return None
    kind = (match.group("kind") or original.kind).casefold()
    if kind == "one":
        kind = original.kind
    if kind not in {original.kind, "folder", "directory", "item"}:
        return None
    kind = original.kind if kind == "item" else kind
    reference = match.group("reference").casefold()
    ordinal = _ORDINALS.get(reference)
    if ordinal is None and reference.isdigit():
        ordinal = int(reference)
    elif ordinal is None and reference[:-2].isdigit():
        ordinal = int(reference[:-2])
    if ordinal is not None and not 1 <= ordinal <= 10:
        return None
    if ordinal is None and reference not in {"last", "selected", "highlighted"}:
        return None
    return VisibleTargetIntent(
        original.verb, kind, ordinal=ordinal, last=reference == "last",
        selected=reference in {"selected", "highlighted"},
    )


def resolve_visible_target(
    observation: DesktopObservation,
    intent: VisibleTargetIntent,
    *,
    folder_names: frozenset[str] = frozenset(),
    ocr_locations: dict[str, ScreenLabelLocation] | None = None,
    expected_applications: frozenset[str] | None = None,
    prior_target: ElementIdentity | None = None,
) -> VisibleTargetBinding:
    """Bind one visible target to a fresh app/window/collection observation."""
    if not observation.complete:
        raise VisibleTargetAmbiguous("I can't see the whole current collection. Which item do you mean?")
    active_frames = [item for item in observation.elements
                     if item.role in _FRAME_ROLES and item.active
                     and item.application not in {"mutter-x11-frames", "gnome-shell"}]
    if len(active_frames) != 1:
        raise VisibleTargetAmbiguous("Which active window should I use?")
    frame = active_frames[0]
    if expected_applications is not None and frame.application.casefold() not in {
        value.casefold() for value in expected_applications
    }:
        raise VisibleTargetAmbiguous("The active window isn't the Files window. Which window should I use?")
    if any(item.application == frame.application and item.active
           and item.role in {"dialog", "alert"}
           and item.path[:len(frame.path)] == frame.path
           for item in observation.elements):
        raise VisibleTargetAmbiguous("A dialog is open. Please close or resolve it first.")

    scoped = [item for item in observation.elements
              if item.application == frame.application and item.path[:len(frame.path)] == frame.path]
    from_prior = False
    if intent.deictic and prior_target is not None:
        prior = [item for item in scoped if ElementIdentity.from_element(item) == prior_target]
        if len(prior) == 1 and _actionable(prior[0], intent):
            candidates = [prior[0]]
            from_prior = True
        else:
            candidates = []
    else:
        candidates = _candidates(scoped, intent, folder_names)

    if not candidates and (intent.selected or intent.deictic):
        selected_item_paths = {
            item.item_path or item.path[:-1]
            for item in scoped if item.selected and item.role not in _FRAME_ROLES
        }
        if len(selected_item_paths) > 1:
            raise VisibleTargetAmbiguous("More than one item is selected. Which one should I open?")
        if len(selected_item_paths) == 1:
            selected_path = next(iter(selected_item_paths))
            candidates = [item for item in _candidates(scoped, intent, folder_names)
                          if (item.item_path or item.path[:-1]) == selected_path]

    if not candidates:
        raise VisibleTargetAmbiguous("I can't identify one selected visible item. Which item do you mean?")

    grouped: dict[tuple[int, ...], list[AccessibleElement]] = {}
    for element in candidates:
        collection_path = element.collection_path or element.path[:-1]
        grouped.setdefault(collection_path, []).append(element)
    if len(grouped) != 1:
        raise VisibleTargetAmbiguous("I see more than one matching collection. Which one do you mean?")
    collection_path, collection = next(iter(grouped.items()))
    collection = _one_target_per_item(collection)
    if (intent.selected or intent.deictic) and not from_prior:
        selected_items = {
            item.item_path or item.path[:-1]
            for item in scoped if item.selected and item.role not in _FRAME_ROLES
        }
        if len(selected_items) > 1:
            raise VisibleTargetAmbiguous("More than one item is selected. Which one should I open?")
        if len(selected_items) != 1:
            raise VisibleTargetAmbiguous("Which visible item do you mean? I don't see one unique selection.")
        selected_path = next(iter(selected_items))
        selected_candidates = [item for item in collection
                               if (item.item_path or item.path[:-1]) == selected_path]
        if len(selected_candidates) != 1:
            raise VisibleTargetAmbiguous("The selected item isn't a unique target. Which one do you mean?")
        ordered = tuple(collection)
        chosen = selected_candidates[0]
        order_method = "current-selection"
    elif from_prior:
        ordered = tuple(collection)
        chosen = collection[0]
        order_method = "current-reference"
    else:
        ordered, order_method = _visible_order(collection, ocr_locations or {})
        index = len(ordered) - 1 if intent.last else (intent.ordinal or 0) - 1
        if index < 0 or index >= len(ordered):
            raise VisibleTargetAmbiguous("That item isn't visible. Which visible item do you mean?")
        chosen = ordered[index]

    identity = ElementIdentity.from_element(chosen)
    collection_signature = [
        [list(item.path), item.role, item.name, list(item.bounds or ()),
         list(item.item_path or item.path[:-1]), list(item.actions),
         item.active, item.focused, item.selected]
        for item in ordered
    ]
    digest = hashlib.sha256(json.dumps(
        [list(collection_path), frame.application, frame.role, frame.name, collection_signature],
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    ordinal = next(index for index, item in enumerate(ordered, start=1)
                   if ElementIdentity.from_element(item) == identity)
    return VisibleTargetBinding(
        identity, ElementIdentity.from_element(frame), chosen.name,
        collection_path, chosen.collection_role or "", chosen.collection_name or "",
        ordinal, len(ordered), order_method, digest, observation.observation_id,
    )


def rebind_visible_target(
    previous: VisibleTargetBinding,
    observation: DesktopObservation,
    intent: VisibleTargetIntent,
    *,
    folder_names: frozenset[str] = frozenset(),
    ocr_locations: dict[str, ScreenLabelLocation] | None = None,
    expected_applications: frozenset[str] | None = None,
) -> VisibleTargetBinding:
    """Re-resolve an owner reference only when its semantic referent is preserved.

    An ordinal never authorizes whichever item happens to occupy its position
    after a change. Recovery requires the same unique item, ordinal, logical
    collection and active window in a fresh observation.
    """
    current = resolve_visible_target(
        observation, intent, folder_names=folder_names,
        ocr_locations=ocr_locations, expected_applications=expected_applications,
    )
    old_window = (
        previous.expected_window.application.casefold(),
        previous.expected_window.role,
        previous.expected_window.name,
    )
    new_window = (
        current.expected_window.application.casefold(),
        current.expected_window.role,
        current.expected_window.name,
    )
    same_referent = (
        old_window == new_window
        and previous.target.application.casefold() == current.target.application.casefold()
        and previous.target.role == current.target.role
        and previous.label == current.label
        and previous.ordinal == current.ordinal
        and previous.collection_path == current.collection_path
        and previous.collection_role == current.collection_role
        and previous.collection_name == current.collection_name
    )
    if not same_referent:
        raise VisibleTargetAmbiguous(
            "The visible collection changed, so I can't confirm the same item. Which item do you mean?"
        )
    return current


def _actionable(element: AccessibleElement, intent: VisibleTargetIntent) -> bool:
    if intent.verb == "open":
        return bool(set(element.actions) & {
            "link.open", "default.activate", "activate", "click", "press", "jump",
        })
    return bool(set(element.actions) & _ACTIONS)


def _candidates(
    scoped: list[AccessibleElement], intent: VisibleTargetIntent,
    folder_names: frozenset[str],
) -> list[AccessibleElement]:
    if intent.kind in {"folder", "directory", "file"}:
        if not folder_names and intent.kind in {"folder", "directory", "file"}:
            raise VisibleTargetAmbiguous("I don't have a trusted location for this collection. Which folder should I use?")
        role_set = _FOLDER_ROLES
        matches = [item for item in scoped
                   if item.role in role_set and item.name in folder_names
                   and "link.open" in item.actions
                   and (item.collection_role in _COLLECTION_ROLES
                        or item.collection_path is None)
                   and item.collection_name.casefold() != "sidebar"]
    else:
        role_set = {
            "button": {"button", "push button"}, "link": {"link"},
            "row": {"table row", "list item", "tree item"},
            "entry": {"entry", "text", "text entry", "combo box"},
            "result": {"link", "list item", "table row"},
            "control": {"button", "push button", "menu item", "link"},
            "item": {"table cell", "list item", "tree item", "icon", "link", "label"},
        }.get(intent.kind, set())
        matches = [item for item in scoped if item.role in role_set and item.name
                   and _actionable(item, intent)
                   and (item.collection_role in _COLLECTION_ROLES
                        or item.collection_path is None)]
    return [item for item in matches if _actionable(item, intent)]


def _one_target_per_item(elements: list[AccessibleElement]) -> list[AccessibleElement]:
    grouped: dict[tuple[int, ...], list[AccessibleElement]] = {}
    for element in elements:
        grouped.setdefault(element.item_path or element.path[:-1], []).append(element)
    targets = []
    for path, group in grouped.items():
        preferred = [item for item in group if "link.open" in item.actions]
        if not preferred:
            preferred = [item for item in group if set(item.actions) & _ACTIONS]
        if len(preferred) != 1:
            raise VisibleTargetAmbiguous("I can't distinguish the visible items safely. Which one do you mean?")
        targets.append(preferred[0])
    if len({item.name for item in targets}) != len(targets):
        raise VisibleTargetAmbiguous("The visible collection has duplicate labels. Which item do you mean?")
    return targets


def _visible_order(
    elements: list[AccessibleElement], locations: dict[str, ScreenLabelLocation],
) -> tuple[tuple[AccessibleElement, ...], str]:
    if len(elements) == 1:
        return (elements[0],), "semantic-geometry"
    bounds = [item.bounds for item in elements]
    reliable = all(value is not None and value[2] > 0 and value[3] > 0 for value in bounds)
    if reliable:
        positions = [(value[0], value[1]) for value in bounds if value is not None]
        reliable = len(set(positions)) == len(positions)
    if reliable:
        return _row_major(elements, {item.name: item.bounds for item in elements}), "semantic-geometry"
    if any(item.name not in locations for item in elements):
        raise VisibleTargetOrderUnavailable(
            "I can't establish the visible order reliably. Which item do you mean?",
            labels=tuple(item.name for item in elements),
        )
    location_bounds = {item.name: locations[item.name].bounds for item in elements}
    if len(set(location_bounds.values())) != len(location_bounds):
        raise VisibleTargetAmbiguous("The visible order is unclear. Which item do you mean?")
    return _row_major(elements, location_bounds), "local-ocr-geometry"


def _row_major(
    elements: list[AccessibleElement], bounds: dict[str, tuple[int, int, int, int] | None],
) -> tuple[AccessibleElement, ...]:
    positioned = []
    for element in elements:
        box = bounds.get(element.name)
        if box is None or box[2] <= 0 or box[3] <= 0:
            raise VisibleTargetAmbiguous("I can't establish the visible order reliably. Which item do you mean?")
        positioned.append((element, box))
    positioned.sort(key=lambda pair: (pair[1][1] + pair[1][3] / 2,
                                      pair[1][0] + pair[1][2] / 2))
    rows: list[list[tuple[AccessibleElement, tuple[int, int, int, int]]]] = []
    for pair in positioned:
        _element, box = pair
        center_y = box[1] + box[3] / 2
        row = next((candidate for candidate in rows
                    if abs(center_y - sum(b[1] + b[3] / 2 for _, b in candidate) / len(candidate))
                    <= max(3.0, min(box[3], min(b[3] for _, b in candidate)) * 0.5)), None)
        if row is None:
            rows.append([pair])
        else:
            row.append(pair)
    ordered = []
    for row in rows:
        ordered.extend(element for element, _box in sorted(row, key=lambda pair: pair[1][0]))
    return tuple(ordered)
