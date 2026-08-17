from __future__ import annotations

import re

PROFILE_BY_SCORE = {
    3: "location_pastor",
    4: "group_pastor",
    5: "region_pastor",
    6: "state_overseer",
    7: "national_admin",
    8: "continental_admin",
    9: "global_admin",
}

STATE_CODE_BY_NAME = {
    "abia": "AB",
    "abia state": "AB",
    "abia_state": "AB",
    "adamawa": "AD",
    "adamawa state": "AD",
    "adamawa_state": "AD",
    "akwa ibom": "AK",
    "akwa ibom state": "AK",
    "akwa_ibom": "AK",
    "akwa_ibom_state": "AK",
    "anambra": "AN",
    "anambra state": "AN",
    "anambra_state": "AN",
    "bauchi": "BA",
    "bauchi state": "BA",
    "bauchi_state": "BA",
    "bayelsa": "BY",
    "bayelsa state": "BY",
    "bayelsa_state": "BY",
    "benue": "BN",
    "benue state": "BN",
    "benue_state": "BN",
    "borno": "BO",
    "borno state": "BO",
    "borno_state": "BO",
    "cross river": "CR",
    "cross river state": "CR",
    "cross_river": "CR",
    "cross_river_state": "CR",
    "delta": "DT",
    "delta state": "DT",
    "delta_state": "DT",
    "ebonyi": "EB",
    "ebonyi state": "EB",
    "ebonyi_state": "EB",
    "edo": "ED",
    "edo state": "ED",
    "edo_state": "ED",
    "ekiti": "EK",
    "ekiti state": "EK",
    "ekiti_state": "EK",
    "enugu": "EN",
    "enugu state": "EN",
    "enugu_state": "EN",
    "fct": "FC",
    "federal capital territory": "FC",
    "federal capital territory abuja": "FC",
    "gombe": "GM",
    "gombe state": "GM",
    "gombe_state": "GM",
    "imo": "IM",
    "imo state": "IM",
    "imo_state": "IM",
    "jigawa": "JG",
    "jigawa state": "JG",
    "jigawa_state": "JG",
    "kaduna": "KD",
    "kaduna state": "KD",
    "kaduna_state": "KD",
    "kano": "KN",
    "kano state": "KN",
    "kano_state": "KN",
    "katsina": "KT",
    "katsina state": "KT",
    "katsina_state": "KT",
    "kebbi": "KB",
    "kebbi state": "KB",
    "kebbi_state": "KB",
    "kwara state": "KW",
    "kwara_state": "KW",
    "kwara": "KW",
    "lagos": "LG",
    "lagos state": "LG",
    "lagos_state": "LG",
    "nasarawa": "NS",
    "nasarawa state": "NS",
    "nasarawa_state": "NS",
    "niger": "NG",
    "niger state": "NG",
    "niger_state": "NG",
    "ogun": "OG",
    "ogun state": "OG",
    "ogun_state": "OG",
    "ondo": "ON",
    "ondo state": "ON",
    "ondo_state": "ON",
    "osun": "OS",
    "osun state": "OS",
    "osun_state": "OS",
    "oyo": "OY",
    "oyo state": "OY",
    "oyo_state": "OY",
    "plateau": "PL",
    "plateau state": "PL",
    "plateau_state": "PL",
    "rivers": "RV",
    "rivers state": "RV",
    "rivers_state": "RV",
    "sokoto": "SK",
    "sokoto state": "SK",
    "sokoto_state": "SK",
    "taraba": "TR",
    "taraba state": "TR",
    "taraba_state": "TR",
    "yobe": "YB",
    "yobe state": "YB",
    "yobe_state": "YB",
    "zamfara": "ZF",
    "zamfara state": "ZF",
    "zamfara_state": "ZF",
    "kogi state": "KG",
    "kogi_state": "KG",
    "kogi": "KG",
}


def profile_key_for_score(score: int) -> str:
    if score <= 3:
        return "location_pastor"
    return PROFILE_BY_SCORE.get(score, "global_admin")


def split_scope_path(path: str | None) -> dict[str, str]:
    cleaned = (path or "").strip()
    if not cleaned:
        return {}
    parts = cleaned.split(".")
    data: dict[str, str] = {}
    code_fields = (
        ("nation_code", "nation_id"),
        ("state_code", "state_id"),
        ("region_code", "region_id"),
        ("group_code", "group_id"),
        ("location_code", "location_id"),
        ("fellowship_code", "fellowship_id"),
    )
    for index, (code_key, legacy_key) in enumerate(code_fields, start=1):
        if len(parts) > index:
            data[code_key] = parts[index]
            # Backward-compatible alias: path segments are display codes, not DB UUIDs.
            data[legacy_key] = parts[index]
    return data


MOCK_NATION_CODES = {
    "nigeria": "234",
}

MOCK_STATE_CODES = {
    "kwara_state": "KW",
    "lagos_state": "LG",
    "kogi_state": "KG",
}

MOCK_CONTINENT_CODES = {
    "west_africa": "WAD",
}

MOCK_REGION_CODES = {
    "ilorin_region": "ILR",
    "ilorin_north_region": "ILN",
}

MOCK_GROUP_CODES = {
    "ilorin_east_group": "ILE",
}

MOCK_LOCATION_CODES = {
    "gra_dlbc": "001",
    "dlcf_kwara_poly": "001",
    "university_dlbc": "002",
    "dlcf_college": "002",
    "tanke_dlbc": "003",
    "dlcf_living_spring": "003",
    "hill_dlcf": "004",
    "dlcf_day_spring": "004",
    "offa_township_dlbc": "001",
    "surulere_dlbc": "001",
}


def _compact_three(slug: str) -> str:
    words = [
        word
        for word in slug.lower().split("_")
        if word and word not in {"state", "region", "group", "division", "global"}
    ]
    if not words:
        return "UNK"
    if len(words) == 1:
        return words[0][:3].upper().ljust(3, "X")
    return f"{words[0][:2]}{words[1][:1]}".upper()


def _format_mock_scope_display_id(path: str) -> str:
    segments = [segment.strip().lower() for segment in path.split(".") if segment.strip()]
    if not segments:
        return ""
    if segments == ["global"]:
        return "DCM"
    parts = ["DCM"]
    if len(segments) > 1:
        continent_code = MOCK_CONTINENT_CODES.get(segments[1])
        if continent_code and len(segments) == 2:
            parts.append(continent_code)
            return "-".join(parts)
    if len(segments) > 2:
        parts.append(MOCK_NATION_CODES.get(segments[2], segments[2].upper()))
    if len(segments) > 3:
        parts.append(MOCK_STATE_CODES.get(segments[3], _compact_three(segments[3])[:2]))
    if len(segments) > 4:
        parts.append(MOCK_REGION_CODES.get(segments[4], _compact_three(segments[4])))
    if len(segments) > 5:
        parts.append(MOCK_GROUP_CODES.get(segments[5], _compact_three(segments[5])))
    if len(segments) > 6:
        location_segment = segments[6]
        parts.append(MOCK_LOCATION_CODES.get(location_segment, "001"))
    if len(segments) > 7:
        fellowship_code = re.sub(r"[^A-Za-z0-9]", "", segments[7]).upper()[:4] or "F001"
        parts.append(fellowship_code)
    return "-".join(parts)


def format_scope_display_id(path: str | None) -> str:
    cleaned = (path or "").strip()
    if not cleaned:
        return ""
    if cleaned.lower().startswith("global"):
        return _format_mock_scope_display_id(cleaned)
    segments = [segment.strip() for segment in cleaned.split(".") if segment.strip()]
    if not segments:
        return ""
    segments[0] = "DCM"
    return "-".join(segment.upper() for segment in segments)


def state_code(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    normalized = raw.lower().replace("-", " ").replace("/", " ")
    if normalized in STATE_CODE_BY_NAME:
        return STATE_CODE_BY_NAME[normalized]
    compact = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if len(compact) == 2:
        return compact
    return compact[:2]


def normalize_public_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("234") and len(digits) > 10:
        return digits[3:]
    if digits.startswith("0") and len(digits) > 1:
        return digits[1:]
    return digits


def format_public_person_code(state_name_or_code: str | None, phone: str | None) -> str:
    code = state_code(state_name_or_code)
    number = normalize_public_phone(phone)
    if not code and not number:
        return ""
    return f"{code}{number}" if code else number
