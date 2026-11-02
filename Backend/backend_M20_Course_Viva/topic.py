"""What a viva's pages are about, said from the pages' own words (2026-11-02).

The warm-up used to be one sentence for every viva that was on a part of a
document: "In your own words, what do these pages cover?" — the same opener for
a deck on reinforcement learning as for one on operating systems, and a question
about the pages rather than about what they teach (the user, 2026-10-31: "all
say the same question what do these pages cover … they should ask from content
not headings").

So the warm-up names the subject. It is found the way a reader would: the
phrase the pages keep coming back to. Two or three words in a row, counted by
how many of the pages say them, with the words that only organise a document
(slide, batch, notes, summary, questions…) breaking a phrase rather than being
part of one — "Monte Carlo" in a Monte Carlo deck, not "Slides 31–40".

No model and no list of subjects: a phrase is topical only because the pages
say it often. And it says nothing when nothing stands out (`phrase` returns
None), because a warm-up about the wrong thing is worse than going straight to
the first question.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

#: Words that end a phrase: function words, and words that only point.
_STOP = frozenset(
    "a an the of to in on for and or but is are was were be been being it its this that these "
    "those with by from as at into than then so such which who whom whose what when where why "
    "how can could should would will shall may might must do does did not no yes if each every "
    "any all some one two more most less least very also only just used use using we you your "
    "our their they he she i me my us there here per via vs eg ie etc".split()
)
#: Words that only organise a document, in any course: a deck's own furniture.
_FURNITURE = frozenset(
    "ppt ppts pptx slide slides summary recap revision agenda contents outline thanks thank "
    "references reference lecture lectures homework assignment quiz introduction overview "
    "conclusion question questions mark marks important formulas sheet quick key insight "
    "example examples exercise exercises study notes".split()
)
#: Words that are furniture only as a label - "Page 3", "Batch 4", "Step 4" -
#: and a subject otherwise: page replacement is an operating systems course's
#: whole subject, and batch normalisation a deep learning one's.
_LABELLED = frozenset(
    "page pages batch batches figure fig table step unit module chapter part section topic".split()
)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9\-']*|\d+")
#: A word shorter than this is an acronym or a fragment ("xed", from a "fi"
#: ligature the PDF lost), not half of a subject's name.
_MIN_WORD = 4
#: The share of the pages that must say a phrase for it to be their subject.
_SHARE = 0.3


def _phrases(text: str):
    """The two- and three-word runs of one line's content words."""
    run: list[str] = []
    for token in [*_TOKEN.findall(text), ""]:
        lowered = token.lower()
        if token.isdigit() and run and run[-1].lower() in _LABELLED:
            run.pop()  # "Page 3": a label, not a word of the subject
        content = (
            token
            and not token.isdigit()
            and lowered not in _STOP
            and lowered not in _FURNITURE
            and len(lowered) >= _MIN_WORD
        )
        if content:
            run.append(token)
            continue
        for size in (2, 3):
            for start in range(len(run) - size + 1):
                yield run[start : start + size]
        run = []


def labels_the_notes(line: str) -> bool:
    """A heading that names the notes, not a subject: "Contents: all batches",
    "Reinforcement learning class test study notes" - a word of the deck's own
    furniture in it, or nothing but function words."""
    words = [word.lower() for word in _TOKEN.findall(line) if not word.isdigit()]
    return any(word in _FURNITURE for word in words) or all(word in _STOP for word in words)


def phrase(pages: list[str]) -> str | None:
    """The phrase most of `pages` say, or None when none stands out."""
    if not pages:
        return None
    said_on: dict[str, set[int]] = defaultdict(set)
    times: Counter[str] = Counter()
    spelt: dict[str, Counter[str]] = defaultdict(Counter)
    for number, text in enumerate(pages):
        for line in text.splitlines():
            for words in _phrases(line):
                key = " ".join(word.lower() for word in words)
                said_on[key].add(number)
                times[key] += 1
                spelt[key][" ".join(words)] += 1
    need = max(2, math.ceil(len(pages) * _SHARE))
    standing = [key for key, on in said_on.items() if len(on) >= need]
    if not standing:
        return None
    best = max(standing, key=lambda key: (len(said_on[key]), times[key], len(key)))
    written = spelt[best].most_common(1)[0][0]
    first, *rest = written.split()
    # A heading's capital is not part of the name: "Backup diagrams" is said
    # "backup diagrams"; "Monte Carlo" keeps both.
    if rest and all(word[:1].islower() for word in rest):
        first = first[:1].lower() + first[1:]
    return " ".join([first, *rest])
