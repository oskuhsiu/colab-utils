"""Opt-in exact references over the existing plan assets; no I/O or inference."""
from __future__ import annotations

import copy
import re
import unicodedata

from workflow import identifier

COLLECTIONS = {"character": "characters", "scene": "scenes", "prop": "props", "voice": "voices"}
TOKEN = re.compile(r"@\{(character|scene|prop):([^{}:/]+)/([^{}:/]+)/([^{}:/]+)\}")
CATALOG_FIELDS = {"name", "aliases", "references", "voice_id"}


def _label(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Reference names must be nonempty strings")
    return unicodedata.normalize("NFC", value.strip())


def lookup(plan, kind, query):
    """Stable IDs are canonical. @name/aliases are exact, case-sensitive NFC.

    An unprefixed exact ID wins; an @name must be unambiguous even when it
    collides with another record's ID. There is no substring/fuzzy lookup.
    """
    if kind not in COLLECTIONS:
        raise ValueError(f"Unknown reference kind: {kind}")
    rows = plan.get(COLLECTIONS[kind], [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{COLLECTIONS[kind]} must be a list of objects")
    ids = [identifier(row.get("id")) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate {kind} IDs")
    query = _label(query)
    if not query.startswith("@") and query in ids:
        return rows[ids.index(query)]
    name = _label(query[1:] if query.startswith("@") else query)
    matches = []
    for row in rows:
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError(f"{kind} aliases must be a list")
        names = [row["id"], *aliases]
        if "name" in row:
            names.append(row["name"])
        if name in {_label(value) for value in names}:
            matches.append(row)
    if len(matches) != 1:
        raise ValueError(f"{'Ambiguous' if matches else 'Missing'} {kind} reference {query!r}; use an exact ID")
    return matches[0]


def voice_binding(plan, character_query):
    character = lookup(plan, "character", character_query)
    voice = lookup(plan, "voice", identifier(character.get("voice_id")))
    if voice["id"] != character["voice_id"]:
        raise ValueError("character.voice_id must be a canonical voice ID, not an alias")
    description = voice.get("description", "")
    if not isinstance(description, str):
        raise ValueError("Voice description must be text")
    return dict(character_id=character["id"], voice_id=voice["id"], description=description)


def image_reference(plan, value):
    if isinstance(value, str):
        match = TOKEN.fullmatch(value)
        if not match:
            raise ValueError("Use @{kind:ID/variant/view} or an explicit kind/ref/variant/view object")
        value = dict(zip(("kind", "ref", "variant", "view"), match.groups()))
    if not isinstance(value, dict) or set(value) != {"kind", "ref", "variant", "view"}:
        raise ValueError("Image references need exactly kind, ref, variant and view")
    kind = value["kind"]
    if kind not in ("character", "scene", "prop"):
        raise ValueError("Image reference kind must be character, scene or prop")
    entity = lookup(plan, kind, value["ref"])
    variant, view = identifier(value["variant"]), identifier(value["view"])
    variants = entity.get("references", {})
    if not isinstance(variants, dict) or not isinstance(variants.get(variant), dict) or view not in variants[variant]:
        raise ValueError(f"Missing {kind} {entity['id']} variant/view {variant}/{view}; no fallback image is selected")
    asset_id = identifier(variants[variant][view])
    if asset_id not in plan.get("assets", {}):
        raise ValueError(f"Reference points to missing asset: {asset_id}")
    return dict(kind=kind, id=entity["id"], variant=variant, view=view, asset_id=asset_id)


def _key(binding):
    return tuple(binding[key] for key in ("kind", "id", "variant", "view"))


def resolve_shot(plan, shot, settings):
    """Compile only declared inputs; picture numbering follows the real adapter.

    No new image is injected from prose. The unchanged asset validation still
    owns ready status, content hashes, supported modality and identity lineage.
    """
    shot = copy.deepcopy(shot)
    inputs = shot.get("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be an object")
    bindings = []
    for role, values in list(inputs.items()):
        if (role == "references") != isinstance(values, list):
            raise ValueError("references must be an ordered list; other input roles name one asset")
        values = values if isinstance(values, list) else [values]
        resolved = []
        for index, value in enumerate(values):
            if isinstance(value, dict) or (isinstance(value, str) and value.startswith("@")):
                if role not in ("first_frame", "last_frame", "references"):
                    raise ValueError("Named image references are only supported for actual image input roles")
                binding = image_reference(plan, value)
                bindings.append(dict(binding, role=role, index=index))
                resolved.append(binding["asset_id"])
                if binding["kind"] == "character":
                    characters = shot.setdefault("characters", [])
                    if binding["id"] not in characters:
                        characters.append(binding["id"])
            else:
                resolved.append(value)
        inputs[role] = resolved if role == "references" else resolved[0] if len(resolved) == 1 else resolved
    if "inputs" in shot:
        shot["inputs"] = inputs
    prompt = shot.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("A final model-specific prompt must be text")
    def resolve_prompt(prompt):
        if "@{" not in prompt:
            return prompt
        if settings.get("backend") != "h3":
            raise ValueError("Picture prompt tokens are supported only by the H3 adapter; other backends may use resolved inputs without tokens")
        roles = ["references"] if settings.get("task_mode") == "ref2va" else [r for r in ("first_frame", "last_frame") if r in inputs]
        actual = [asset for role in roles for asset in (inputs[role] if role == "references" else [inputs[role]])]
        def replace(match):
            reference = image_reference(plan, match.group())
            # A token can name an explicitly supplied legacy asset ID as well.
            positions = [i + 1 for i, asset in enumerate(actual) if asset == reference["asset_id"]]
            if len(positions) != 1:
                raise ValueError("Prompt reference needs exactly one matching actual image input; do not inject or guess picture order")
            if not any(_key(item) == _key(reference) for item in bindings):
                bindings.append(dict(reference, role="prompt", picture=positions[0]))
            if reference["kind"] == "character" and reference["id"] not in shot.setdefault("characters", []):
                shot["characters"].append(reference["id"])
            return f"<Picture {positions[0]}>"
        prompt = TOKEN.sub(replace, prompt)
        if "@{" in prompt:
            raise ValueError("Malformed or unsupported reference token; use @{kind:ID/variant/view}")
        return prompt
    if "prompt" in shot:
        shot["prompt"] = resolve_prompt(prompt)
    timing = shot.get("dialogue_timing")
    if isinstance(timing, dict):
        beats = timing.get("action_beats", [])
        if isinstance(beats, list):
            for beat in beats:
                if isinstance(beat, dict) and isinstance(beat.get("description"), str):
                    beat["description"] = resolve_prompt(beat["description"])
        for line in timing.get("utterances", []):
            if "speaker_ref" not in line:
                continue
            if "speaker" in line or "voice_id" in line or "voice_description" in line:
                raise ValueError("speaker_ref replaces manual speaker/voice fields; do not specify both")
            voice = voice_binding(plan, line.pop("speaker_ref"))
            line.update(speaker=voice["character_id"], voice_id=voice["voice_id"], voice_description=voice["description"])
    if bindings:
        shot["reference_bindings"] = bindings
    return shot


def generation_character(character):
    """Lookup labels and unused views are not generation inputs."""
    return {key: value for key, value in character.items() if key not in CATALOG_FIELDS}
