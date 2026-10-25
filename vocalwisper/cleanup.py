"""Cleanup of whisper output: repeated phrases, loops, stray punctuation."""

import re

# word (letters, digits, apostrophes) optionally followed by punctuation
_TOKEN_RE = re.compile(r"\S+")
_STRIP_RE = re.compile(r"^[^\wàèéìòùáíóúâêîôûäëïöü]+|[^\wàèéìòùáíóúâêîôûäëïöü]+$",
                       re.IGNORECASE)


def _key(token: str) -> str:
    return _STRIP_RE.sub("", token.lower())


def _collapse(tokens, n, min_run):
    """Collapse runs of the same n-gram (>= min_run) down to one occurrence."""
    out = []
    keys = [_key(t) for t in tokens]
    i = 0
    total = len(tokens)
    while i < total:
        run = 1
        while (i + (run + 1) * n <= total
               and keys[i:i + n] == keys[i + run * n:(i + run * n) + n]):
            run += 1
        if run >= min_run:
            out.extend(tokens[i:i + n])
            i += run * n
        else:
            out.append(tokens[i])
            i += 1
    return out


def clean_repetitions(text: str) -> str:
    """Remove whisper loop artifacts like "same phrase, same phrase, ..."."""
    if not text:
        return ""
    tokens = _TOKEN_RE.findall(text)
    if len(tokens) < 2:
        return text.strip()

    for _ in range(3):
        before = len(tokens)
        # long repeated phrases are always an artifact
        for n in range(12, 3, -1):
            tokens = _collapse(tokens, n, 2)
        # single words only when repeated at least three times
        for n in (3, 2):
            tokens = _collapse(tokens, n, 3 if n == 3 else 2)
        tokens = _collapse(tokens, 1, 3)
        if len(tokens) == before:
            break

    # a phrase repeated right after itself with different casing/punctuation
    out = " ".join(tokens)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"([,.;:!?])\1+", r"\1", out)
    return out.strip()


def is_hallucination(text: str) -> bool:
    """Common whisper hallucinations on silence/music/noise."""
    t = text.strip().lower().strip(" .,!¡?¿")
    if not t:
        return True
    patterns = (
        r"grazie (per|a tutti)",
        r"sottotitoli (e revisione )?a cura di",
        r"(iscriviti|subscribe).*(canale|channel)",
        r"ci vediamo (nel|al) prossimo video",
        r"buona visione",
    )
    if any(re.search(p, t) for p in patterns):
        return True
    # same word repeated over and over: nothing useful was said
    words = re.findall(r"\w+", t)
    if len(words) >= 6 and len(set(words)) <= max(2, len(words) // 5):
        return True
    return False


_FILLERS = {"e", "eh", "ehm", "eee", "mh", "mm", "mmm", "ah", "uh", "hm"}
_THANKS = {"grazie", "grazie mille", "grazie a tutti", "ciao", "a presto", "buonanotte"}


def is_filler(text: str, confidence: float = 1.0) -> bool:
    """Lone fillers/thanks that whisper invents on noise (thanks only if unsure)."""
    t = " ".join(re.findall(r"\w+", text.lower()))
    if t in _FILLERS:
        return True
    return t in _THANKS and confidence < 0.85
