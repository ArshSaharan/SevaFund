"""Stage 1-2: document extraction and structured evidence normalization.

Turns raw document text (as produced by ``app.services.rag.extract_document_text``)
into typed fields - people, organisations, dates, rupee amounts, identifiers and
service descriptions - each carrying the document title, page and chunk it came
from.  Chunk numbers follow ``rag.chunk_document`` so a reviewer can find the
same passage in the retrieval layer.

Extraction is deterministic and conservative: when a value cannot be read with
confidence it is omitted (or given a low confidence) rather than guessed.
"""
import bisect
import re
from typing import Iterator, List, Optional, Tuple

from app.services.rag import CHUNK_OVERLAP, CHUNK_WORDS

from .money import find_amounts, parse_amount_field
from .normalize import HONORIFICS, find_dates, normalize_id
from .schemas import CaseInput, DocumentEvidence, DocumentInput, ExtractedField, SourceRef

CAMPAIGN_TEXT = "Campaign text"

# ---------------------------------------------------------------- vocabulary
_ORG_KEYWORDS = {
    "hospital", "hospitals", "clinic", "institute", "college", "university", "school", "academy", "polytechnic",
    "vidyalaya", "trust", "foundation", "society", "samiti", "mandal", "sangh", "samuh", "sangam", "sangathan",
    "sanstha", "association", "club", "federation", "centre", "center", "bank", "panchayat", "police",
    "department", "office", "government", "registrar", "traders", "agencies", "agency", "enterprises",
    "constructions", "borewells", "bhandar", "stores", "suppliers", "contractors", "industries", "associates",
    "diagnostics", "imaging", "laboratory", "laboratories", "pharmacy", "medicals", "mission", "council",
    "board", "corporation", "ngo", "parishad", "sabha", "builders", "electricals", "distributors",
    "sangha", "samithi", "kendra", "mandali", "samaj", "manch", "nyas",
    "systems", "solutions", "works", "motors", "engineers", "technologies", "sons", "company", "pumps",
    "electronics", "hardware", "furniture", "opticals", "surgicals", "printers", "travels", "caterers",
}
_VENDOR_WORDS = {"traders", "agencies", "agency", "enterprises", "constructions", "borewells", "bhandar", "stores",
                 "suppliers", "contractors", "industries", "associates", "pharmacy", "medicals", "builders",
                 "electricals", "distributors", "systems", "solutions", "works", "motors", "engineers",
                 "technologies", "sons", "company", "pumps", "electronics", "hardware", "furniture", "opticals",
                 "surgicals", "printers", "travels", "caterers"}
_AUTHORITY_WORDS = {"panchayat", "police", "department", "office", "government", "registrar", "council", "board",
                    "corporation", "sabha", "federation"}
_DIAGNOSTIC_WORDS = {"diagnostics", "diagnostic", "imaging", "laboratory", "laboratories", "pathology", "scan"}
_ROLE_WORDS = {"head", "principal", "manager", "coordinator", "officer", "secretary", "president", "director",
               "registrar", "chairperson", "treasurer", "trustee", "sarpanch", "animator", "consultant", "surgeon",
               "dean", "warden", "assistant", "branch", "district", "station", "house", "admissions", "centre",
               "center", "office", "department", "postgraduate"}
_CONNECTORS = {"of", "and", "&", "for", "the"}
_NAME_STOP = {
    "application", "roll", "no", "age", "aged", "class", "hospital", "uhid", "ip", "ipd", "mr", "date", "the",
    "regd", "regn", "ref", "sex", "admission", "enrolment", "enrollment", "student", "patient", "course", "dob",
    "id", "to", "from", "sub", "subject", "dear", "sir", "madam", "this", "that", "is", "has", "was", "will",
    "a", "an", "on", "in", "at", "by", "of", "and", "for", "with", "savings", "personal", "sb", "account",
    "bill", "invoice", "total", "amount", "rs", "inr", "upi", "ifsc", "india", "indian", "government",
    "we", "our", "you", "your", "it", "kindly", "please", "note", "estimate", "certificate", "resolved",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "class", "quarter", "page", "years", "year", "pt", "name", "hospital",
}
_HONORIFIC_RE = re.compile(r"(?:(?:%s)\.?\s+)*" % "|".join(sorted(HONORIFICS, key=len, reverse=True)), re.I)
_NAME_TOKEN = re.compile(r"[A-Z]\.(?=\s|[A-Z])|[A-Z][a-z']+|[A-Z]{2,}(?![a-z])")
_CAP_TOKEN = re.compile(r"[A-Z][\w'.]*|&|of\b|and\b|for\b|the\b")

_SUBJECT_LABEL = re.compile(
    r"^(?:name of (?:the )?)?(?:patient|pt|student|candidate|applicant|beneficiary|baby|child|pupil|trainee)"
    r"(?:'?s)?(?: name)?$|^name$|^billed to$|^issued to$|^full name$")
_GUARDIAN_LABEL = re.compile(r"parent|guardian|mother|father|husband|wife|spouse|next of kin")
_STAFF_LABEL = re.compile(
    r"consultant|doctor|treating|physician|surgeon|neonatologist|nephrologist|oncologist|principal|president|"
    r"trustee|animator|ref by|referred by|chairperson|secretary|treasurer|signatory|prepared by|issued by|"
    r"coordinator")
_PAYEE_LABEL = re.compile(r"payee|account holder|a/c holder|account name|in favou?r of|beneficiary account")
_SERVICE_LABEL = re.compile(
    r"^(?:procedure|surgery performed|surgery|operation|planned treatment|treatment|treatment plan|management|"
    r"advice|plan|course|programme|program|class|work|name of work|nature of work|scope of work|sub|subject|"
    r"supply of|for supply of|purpose|project|service|item|description of work)$")
_ORG_LABEL = re.compile(
    r"^(?:name of (?:the )?)?(?:hospital|institution|institute|college|university|school|society|trust|"
    r"organisation|organization|ngo|group|club)(?: name)?$|^(?:buyer|client|customer|to|kind attn|m/s|"
    r"bill to|consignee)$")
_MONEY_LABEL = re.compile(r"amount|cost|fees?\b|payable|value|bill|estimate|outstanding|due|balance|paid|received|"
                          r"remitted|price|charges|quotation|invoice|arrears|sanction")
_DOC_REF = re.compile(
    r"\b(?:bill|invoice|receipt|ref|reference|quotation|qtn|estimate|est|sheet|pi|memo|resolution|report|order|"
    r"statement|certificate|voucher|sanction order)\.?\s*(?:no\.?|number|#|id)?\s*[:.#\-]?\s*"
    r"([A-Za-z0-9][\w/\-]*\d[\w/\-]*)", re.I)
_ID_VALUE = r"\s*[:.#\-]?\s*(?:is\s+)?([A-Za-z0-9][\w/\-]*\d[\w/\-]*)(?![\w/\-]*,\d)"
_INLINE_IDS = [
    ("patient_id", r"\b(?:uhid|mrn|mr\s*no\.?|hospital\s*no\.?|patient\s*id|cr\s*no\.?)"),
    ("inpatient_id", r"\b(?:ipd?\s*(?:regn\.?\s*|reg\.?\s*)?(?:no\.?|number))"),
    ("roll_no", r"\broll\s*(?:no\.?|number)"),
    ("enrolment_no", r"\benrol+ment\s*(?:no\.?|number)"),
    ("application_no", r"\b(?:application\s*(?:no\.?|number)|applicant\s*reference)"),
    ("admission_no", r"\badmission\s*(?:no\.?|number)"),
    ("student_id", r"\bstudent\s*id"),
    ("pan", r"\bpan(?:\s*no\.?)?"),
    ("registration_no", r"\b(?:registration|regn\.?|regd\.?|reg\.)\s*(?:no\.?|number)?"),
]
_INLINE_ID_RES = [(family, re.compile(pattern + _ID_VALUE, re.I)) for family, pattern in _INLINE_IDS]
_UPI = re.compile(r"\b[\w.\-]{2,}@(?:ok\w+|ybl|upi|paytm|ibl|axl|apl|sbi|icici|hdfcbank|axisbank|oksbi)\b", re.I)

_DATE_ROLES = [
    ("admission", r"\badmission\b|\badmitted\b|\bdoa\b"),
    ("discharge", r"\bdischarged?\b|\bdod\b"),
    ("due", r"last date|\bdue\b|on or before|deadline|\bby\b|payable by|not later than|\bbefore\b"),
    ("procedure", r"\boperated\b|surgery (?:date|on|performed on)|operation (?:date|on)|procedure (?:date|on)"),
    ("meeting", r"held on|meeting (?:date|on|dated)"),
    ("registration", r"date of registration|registered on|registered since"),
    ("birth", r"\bdob\b|date of birth|\bborn\b"),
    ("planned", r"planned|scheduled|expected|tentative|proposed|commenc|starting|begins?"),
    ("validity", r"valid (?:till|until|upto|up to)|expir"),
    ("issue", r"\bdate\b|\bdated\b|\bdt\b|issued|\bsent\b|prepared|\bon record\b"),
]
_DATE_ROLE_RES = [(role, re.compile(pattern, re.I)) for role, pattern in _DATE_ROLES]

_BALANCE_WORDS = re.compile(r"balance|net payable|net amount to be|outstanding|amount due|payable by|remaining|"
                            r"arrears|to be arranged|own contribution|still (?:owed|due)|\bdue\b", re.I)
_PAID_WORDS = re.compile(r"\breceived\b|\bpaid\b|\bremitted\b|\badjusted\b|\bless\b|\bdeposited\b", re.I)
_COVERED_WORDS = re.compile(r"scholarship|waiver|insurance|insurer|\btpa\b|\bgrant\b|subsid|\bloan\b|assistance|"
                            r"scheme|sanction", re.I)
_TOTAL_WORDS = re.compile(r"total|gross|grand|estimate|\bcost\b|invoice|bill\b|quotation|net amount|fee payable|"
                          r"equivalent|fee notice|fee structure|statement|cost sheet|\bamount is\b|letter puts", re.I)
_ASK_WORDS = re.compile(r"rais|request|appeal|target|need|asking|hope|wish|seek", re.I)

_EVIDENCE_KEYWORDS = {
    "cost": r"estimate|quotation|qtn\b|proforma|invoice|\bbill\b|fee (?:demand|structure|notice|statement)|"
            r"arrears|outstanding fees|cost sheet|abstract of cost|budget|fee note|cost note",
    "clinical": r"diagnosis|\bdx\b|impression|findings|admitted|discharge|chemotherapy|surgery|fracture|"
                r"under my care|advised|prognosis|\bicu\b|nicu|clinical|case summary|operat",
    "enrollment": r"bonafide|bona fide|selected for admission|offer you a place|enrolment confirmation|"
                  r"enrollment confirmation|seat .{0,90} reserved|student of this|has been a student|"
                  r"admission letter|provisional admission|is studying",
    "org_identity": r"certificate of registration|registered as a (?:society|trust)|registered at this office|"
                    r"registration certificate|is a member group|societies registration act|trust deed|"
                    r"society registration|registration no|regn\.? no|regd\.? no",
    "authorization": r"resolved|resolution|minutes of|permitted|no.objection|sanction order|work order",
    "beneficiary_info": r"households|beneficiar(?:y|ies) (?:list|summary)|families|members",
}
_EVIDENCE_RES = {name: re.compile(pattern, re.I) for name, pattern in _EVIDENCE_KEYWORDS.items()}
_SIGNATORY = re.compile(r"\b(?:principal|registrar|consultant|surgeon|sarpanch|manager|coordinator|chairperson|"
                        r"secretary|president|trustee|signed|signature|authorised signatory|head of|director|"
                        r"officer|haemato-oncologist|neonatologist|nephrologist)\b", re.I)
_SUBJECT_VERBS = re.compile(r"was admitted|has been a student|is a student|is a bonafide|is under|was diagnosed|"
                            r"is studying|is presently|was treated|is undergoing|has been advised|underwent|"
                            r"is enrolled|has been admitted|was brought", re.I)
_PROSE_PERSON_ANCHORS = [
    ("subject", 0.85, re.compile(r"certif(?:y|ied) that\s+", re.I)),
    ("subject", 0.8, re.compile(r"\bDear\s+")),
    ("subject", 0.7, re.compile(r"\b(?:patient|student|candidate|cyclist|applicant|beneficiary|pedestrian|child|"
                                r"trainee|pupil)\s*,\s+")),
    ("subject", 0.6, re.compile(r"\b(?:estimate|treatment|chemotherapy|surgery|fees? pending|quotation|"
                                r"certificate|letter) for\s+", re.I)),
    ("guardian", 0.8, re.compile(r"\b(?:son|daughter|son/daughter|wife|husband|ward)\s+of\s+|\b[sdwc]/o\.?\s+", re.I)),
    ("payee", 0.85, re.compile(r"(?:a/c holder|account holder|account name|transferred to|payable to|"
                               r"remit(?:ted)? (?:\w+ ){0,3}to|in favou?r of|favouring|pay to|in the name of|"
                               r"routed (?:through|via)[^:\n]{0,40}:\s*account name)\s*:?\s*(?:the\s+)?", re.I)),
]
_PROSE_SERVICE_ANCHORS = [re.compile(pattern, re.I) for pattern in (
    r"(?:has been|is|was|been) advised\s+(.+?)(?:[.;]\s|[.;]$)",
    r"admission to (?:the\s+)?(.+?)(?:\s+for the\b|[.;]\s|[.;]$)",
    r"a place (?:on|in) (?:the\s+)?(.+?)(?:,|[.;]\s|[.;]$)",
    r"studying in\s+(.+?)(?:\s+during\b|[.;]\s|[.;]$)",
    r"seat in (?:the\s+)?(.+?)(?:\s+is\b|[.;]\s|[.;]$)",
    r"(?:carry out|take up|undertake|execute)\s+(.+?)(?:\s+on\b|\s+and to\b|[.;]\s|[.;]$)",
    r"supply of\s+(.+?)(?::|[.;]\s|[.;]$)",
    r"presently in\s+(.+?)(?:[.;]\s|[.;]$)",
    r"(?:enrolled in|undergoing|underwent|scheduled for)\s+(.+?)(?:[.;,]\s|[.;]$)",
    r"cost of\s+(.+?)(?:,|\s+with\b|\s+will\b|\s+including\b|[.;]\s|[.;]$)",
)]


# ------------------------------------------------------------------ helpers
class Locator:
    """Maps a character offset to the page and RAG chunk that contain it."""

    def __init__(self, text: str, title: str, index: int):
        self.text, self.title, self.index = text, title, index
        self.word_starts = [m.start() for m in re.finditer(r"\S+", text)]
        self.pages = [(m.start(), int(m.group(1))) for m in re.finditer(r"\[Page (\d+)\]", text)]

    def ref(self, start: int, end: Optional[int] = None) -> SourceRef:
        word = max(bisect.bisect_right(self.word_starts, start) - 1, 0)
        page = None
        for offset, number in self.pages:
            if offset <= start:
                page = number
        line_start = self.text.rfind("\n", 0, start) + 1
        line_end = self.text.find("\n", end or start)
        excerpt = " ".join(self.text[line_start:line_end if line_end != -1 else len(self.text)].split())
        return SourceRef(document=self.title, doc_index=self.index, page=page,
                         chunk=word // (CHUNK_WORDS - CHUNK_OVERLAP) + 1, excerpt=excerpt[:200])


def flatten(text: str) -> str:
    """Same-length copy with single newlines turned into spaces (offsets preserved)."""
    return re.sub(r"(?<!\n)\n(?!\n)", " ", text)


def sentences(text: str) -> List[Tuple[int, int, str]]:
    """Sentence-like units.  Short lines are treated as stand-alone units
    (forms, tables); long lines are assumed to be wrapped prose and joined."""
    units, start = [], 0
    lines = text.split("\n")
    buffer_start, buffer = None, []
    position = 0

    def flush():
        nonlocal buffer_start, buffer
        if buffer:
            joined = " ".join(buffer)
            offset = buffer_start
            for piece in re.split(r"(?<=[.;!?])\s+", joined):
                if piece.strip():
                    units.append((offset, offset + len(piece), piece.strip()))
                offset += len(piece) + 1
        buffer_start, buffer = None, []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
        else:
            if buffer_start is None:
                buffer_start = position
            buffer.append(line)
            if len(line) < 72:
                flush()
        position += len(line) + 1
    flush()
    return units


def take_entity(text: str) -> Tuple[Optional[str], Optional[str], int]:
    """Read a person or organisation name from the start of ``text``.

    Returns (kind, name, length consumed); kind is "person", "organisation" or None.
    """
    lead = _HONORIFIC_RE.match(text)
    offset = lead.end() if lead else 0
    tokens, position, comma_used = [], offset, False
    while len(tokens) < 9:
        gap = re.match(r"[ \t]?", text[position:])
        cursor = position + gap.end()
        match = _CAP_TOKEN.match(text, cursor)
        if not match:
            if (tokens and len(tokens) == 1 and not comma_used and text[cursor:cursor + 1] == ","
                    and _NAME_TOKEN.match(text, cursor + 1 + len(re.match(r"\s*", text[cursor + 1:]).group(0)))):
                comma_used = True
                position = cursor + 1
                continue
            break
        token = match.group(0)
        if token.casefold() in _CONNECTORS and not tokens:
            break
        tokens.append(token)
        position = match.end()
    while tokens and tokens[-1].casefold() in _CONNECTORS:
        tokens.pop()
    if not tokens:
        return None, None, 0
    lowered = [t.casefold().strip(".'") for t in tokens]
    if any(t in _ORG_KEYWORDS for t in lowered):
        name = " ".join(tokens)
        if is_org_name(name):
            return "organisation", name, position
        return None, None, 0
    person = []
    for token in tokens:
        bare = token.casefold().strip(".'")
        if bare in _CONNECTORS or bare in _NAME_STOP or bare in _ROLE_WORDS or not _NAME_TOKEN.fullmatch(token):
            break
        person.append(token)
        if len(person) == 4:
            break
    if not person or all(len(t.strip(".")) == 1 for t in person):
        return None, None, 0
    return "person", " ".join(person), position


def is_org_name(name: str) -> bool:
    tokens = [t.casefold().strip(".'") for t in re.findall(r"[\w'.&]+", name)]
    has_keyword = any(t in _ORG_KEYWORDS for t in tokens)
    proper = [t for t in tokens if t not in _ORG_KEYWORDS and t not in _ROLE_WORDS and t not in _CONNECTORS
              and t not in _NAME_STOP and len(t) >= 3]
    return has_keyword and bool(proper) and len(tokens) >= 2


def org_kind(name: str) -> str:
    tokens = [t.casefold().strip(".'") for t in re.findall(r"[\w'.&]+", name)]
    if "bank" in tokens:
        return "bank"
    if any(t in _DIAGNOSTIC_WORDS for t in tokens):
        return "diagnostic"
    keywords = [t for t in tokens if t in _ORG_KEYWORDS]
    head = keywords[-1] if keywords else ""
    if head in _VENDOR_WORDS:
        return "vendor"
    if head in _AUTHORITY_WORDS:
        return "authority"
    return "institution"


_PLACE_AFTER = re.compile(r"\s*,\s*([A-Z][a-z]{3,})\b")


def find_orgs(text: str) -> List[Tuple[str, int, int]]:
    """Capitalised runs that contain an organisation keyword and a proper name.

    A run made only of generic words ("Government Polytechnic College") takes
    the place name that follows a comma as its distinguishing part.
    """
    found = []
    for segment in re.finditer(r"[^,;:()\n\t]+", text):
        for part in re.finditer(r"(?:(?!\s{2,}|\s-\s).)+", segment.group(0)):
            base = segment.start() + part.start()
            run_start, run_end, run = None, None, []

            def close():
                tokens = list(run)
                while tokens and tokens[-1][0].casefold() in _CONNECTORS:
                    tokens.pop()
                while tokens and tokens[0][0].casefold() in _CONNECTORS:
                    tokens.pop(0)
                if len(tokens) >= 2:
                    name = text[tokens[0][1]:tokens[-1][2]].rstrip(".,;:'")
                    if is_org_name(name):
                        found.append((" ".join(name.split()), tokens[0][1], tokens[0][1] + len(name)))
                    elif all(t[0].casefold().strip(".'") in _ORG_KEYWORDS | _CONNECTORS for t in tokens):
                        place = _PLACE_AFTER.match(text, tokens[0][1] + len(name))
                        if place and place.group(1).casefold() not in _ORG_KEYWORDS | _NAME_STOP:
                            full = f"{' '.join(name.split())}, {place.group(1)}"
                            found.append((full, tokens[0][1], place.end()))

            cursor = 0
            chunk = part.group(0)
            for word in re.finditer(r"\S+", chunk):
                token = word.group(0)
                is_cap = bool(re.match(r"[A-Z]", token)) or token.casefold() in _CONNECTORS
                if is_cap:
                    run.append((token, base + word.start(), base + word.end()))
                else:
                    close()
                    run = []
                cursor = word.end()
            close()
    return found


def _norm_label(label: str) -> str:
    return " ".join(re.sub(r"[.’]", "", label.casefold()).replace("’", "'").split())


_LABEL_WORDS = set("""
patient patients name pt student candidate applicant beneficiary baby child pupil trainee billed issued to full
parent guardian mother father husband wife spouse next kin consultant doctor treating physician surgeon
neonatologist nephrologist oncologist principal president trustee animator ref by referred chairperson secretary
treasurer signatory prepared coordinator payee account holder a/c in favour favor of procedure surgery performed
operation planned treatment plan management advice course programme program class work nature scope sub subject
supply purpose project service item description hospital institution institute college university school society
trust organisation organization ngo group club buyer client customer kind attn m/s bill consignee no number uhid
ip ipd regn reg regd registration mr roll admission application enrolment enrollment date dt age sex dob id the
amount total status diagnosis dx history invoice receipt quotation qtn estimate ward bed unit department dept
report scan sheet phone mobile address gender payment mode terms remarks note validity programme reference
""".split())


def _is_label_word(token: str) -> bool:
    bare = token.casefold().strip(".:,;'()")
    parts = [part for part in bare.split("/") if part]
    return bool(parts) and all(part in _LABEL_WORDS for part in parts)


def _split_cell(cell: str) -> List[Tuple[str, str, int]]:
    """Split one cell into (label, value, value offset) pairs without relying on
    column spacing: ``Name: A B Hospital No: X`` -> (Name, A B), (Hospital No, X);
    ``Patient A B (neonate)`` -> (Patient, A B (neonate))."""
    colons = [m.start() for m in re.finditer(r":(?![\d/])", cell)]
    words = list(re.finditer(r"[^\s:]+" if colons else r"\S+", cell))
    if not colons:
        k = 0
        while k < len(words) and k < 5 and _is_label_word(words[k].group(0)):
            k += 1
        if 0 < k < len(words) and words[0].group(0)[0].isupper():
            label = cell[:words[k - 1].end()]
            if _known_label(_norm_label(label)):
                return [(label, cell[words[k].start():], words[k].start())]
        return []
    starts: List[Tuple[int, int]] = []
    for colon in colons:
        head = [w for w in words if w.end() <= colon]
        first_value = 0
        if starts:
            first_value = next((i for i, w in enumerate(head) if w.start() > starts[-1][1]), len(head))
        k = len(head)
        while k - 1 >= first_value + (1 if starts else 0) and _is_label_word(head[k - 1].group(0)) and len(head) - k < 4:
            k -= 1
        while k < len(head) and not head[k].group(0)[0].isupper():
            k += 1
        if k < len(head):
            starts.append((head[k].start(), colon))
        elif not starts and head and len(head) <= 6 and re.match(r"[A-Za-z]", head[0].group(0)):
            starts.append((head[0].start(), colon))
    pairs = []
    for index, (label_start, colon) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(cell)
        value = cell[colon + 1:end]
        if value.strip():
            pairs.append((cell[label_start:colon], value.strip(), colon + 1 + len(value) - len(value.lstrip())))
    return pairs


def labelled_cells(text: str) -> Iterator[Tuple[str, str, int]]:
    """Yield (normalized label, value, value offset) for form-style content:
    ``Label: value``, ``Label    value``, ``Label value`` and dotted-leader rows."""
    position = 0
    for line in text.split("\n"):
        work = re.sub(r"\s*\.{3,}\s*", lambda m: " " * len(m.group(0)), line)
        cells = [(m.start(), m.group(0)) for m in re.finditer(r"\S(?:.*?\S)?(?=\s{2,}|\t|\s*$)", work)]
        index = 0
        while index < len(cells):
            offset, cell = cells[index]
            following = cells[index + 1] if index + 1 < len(cells) else None
            if following and re.match(r"^[A-Za-z][^:]{0,44}:$", cell):
                yield _norm_label(cell[:-1]), following[1], position + following[0]
                index += 2
                continue
            if following and following[1].startswith(":") and len(cell.split()) <= 6:
                value = following[1].lstrip(": ")
                yield _norm_label(cell), value, position + following[0] + len(following[1]) - len(value)
                index += 2
                continue
            pairs = _split_cell(cell)
            if pairs:
                for label, value, value_offset in pairs:
                    yield _norm_label(label), value, position + offset + value_offset
                index += 1
            elif following and len(cell.split()) <= 6 and _known_label(_norm_label(cell)):
                yield _norm_label(cell), following[1], position + following[0]
                index += 2
            else:
                index += 1
        position += len(line) + 1


_MONEY_ROW = re.compile(
    r"^(?P<label>[ \t]*[A-Za-z][^\n]*?[A-Za-z)])[ \t]*(?:\.{2,}|:|-)?[ \t]*"
    r"(?P<amount>(?:rs\.?[ \t]*|₹[ \t]*|inr[ \t]*)?\d[\d,]*(?:\.\d+)?(?:/-)?|nil\b[^\n]*)[ \t]*$", re.I | re.M)
_MONEY_ROW_LABEL = re.compile(r"amount|cost|fees?\b|payable|value|bill|estimate|outstanding|\bdue\b|balance|paid|"
                              r"received|remitted|price|charges|quotation|invoice|arrears|sanction|total|deposit", re.I)
_COUNT_NOUNS = re.compile(r"households|students|members|families|kits|\bnos\b|units|days|months|years|weeks|"
                          r"titles|pages|people|persons|beneficiaries|items|\bqty\b|quantity|weight|\bage\b|"
                          r"sessions|cycles|\bno\b|number|date|\bid\b|\bref", re.I)


def _known_label(label: str) -> bool:
    return bool(_SUBJECT_LABEL.search(label) or _GUARDIAN_LABEL.search(label) or _STAFF_LABEL.search(label)
                or _PAYEE_LABEL.search(label) or _SERVICE_LABEL.search(label) or _ORG_LABEL.search(label)
                or _MONEY_LABEL.search(label) or re.search(r"\bdate\b|\bdt\b|\bno\b|\bnumber\b|\bid\b", label))


def amount_role(prefix: str, suffix: str = "") -> str:
    """Role of an amount from the words that introduce (and follow) it."""
    if _BALANCE_WORDS.search(prefix):
        return "balance"
    if _PAID_WORDS.search(prefix):
        return "paid"
    if _COVERED_WORDS.search(prefix):
        return "covered"
    if _TOTAL_WORDS.search(prefix):
        return "total"
    if _PAID_WORDS.search(suffix):
        return "paid"
    if _COVERED_WORDS.search(suffix):
        return "covered"
    if _ASK_WORDS.search(prefix):
        return "ask"
    return "line_item"


def _date_role(context: str, standalone: bool) -> str:
    best_role, best_end = ("issue" if standalone else "other"), -1
    for role, pattern in _DATE_ROLE_RES:
        for match in pattern.finditer(context):
            if match.end() > best_end:
                best_role, best_end = role, match.end()
    return best_role


# ----------------------------------------------------------------- extraction
def _extract_fields(text: str, locator: Locator, is_campaign: bool) -> List[ExtractedField]:
    fields: List[ExtractedField] = []
    flat = flatten(text)

    def add(kind, role, raw, value, start, end=None, confidence=0.8):
        fields.append(ExtractedField(kind=kind, role=role, raw=raw.strip(), value=value, confidence=confidence,
                                     source=locator.ref(start, end)))

    # --- rupee amounts carrying a currency marker ---------------------------
    marked_spans = []
    previous_end = 0
    for mention in find_amounts(text):
        line_start = text.rfind("\n", 0, mention.start) + 1
        line_end = text.find("\n", mention.end)
        if (line_end if line_end != -1 else len(text)) - line_start < 72:
            clause_start = line_start          # form/table row: the row is the context
        else:                                  # wrapped prose: back to the sentence start
            window_start = max(flat.rfind("\n\n", 0, mention.start) + 1, mention.start - 200, 0)
            breaks = [m.end() for m in re.finditer(r"[.;]\s+(?=[A-Z])", flat[window_start:mention.start])]
            clause_start = window_start + (breaks[-1] if breaks else 0)
        prefix = flat[max(clause_start, previous_end):mention.start]
        stop = re.search(r"[.;\n]|₹|\brs\b|\binr\b", flat[mention.end:mention.end + 90], re.I)
        suffix = flat[mention.end:mention.end + (stop.start() if stop else 90)]
        previous_end = mention.end
        marked_spans.append((mention.start, mention.end))
        if not mention.valid:
            add("amount", "invalid", mention.raw, None, mention.start, mention.end, 0.0)
            continue
        add("amount", amount_role(prefix, suffix), mention.raw, mention.value, mention.start, mention.end, 0.9)

    # --- form-style cells ----------------------------------------------------
    amount_offsets = set()
    for label, value, offset in labelled_cells(text):
        end = offset + len(value)
        dates = find_dates(value)
        if _SUBJECT_LABEL.search(label) or _GUARDIAN_LABEL.search(label) or _PAYEE_LABEL.search(label) \
                or _STAFF_LABEL.search(label):
            kind, name, _ = take_entity(value)
            role = ("guardian" if _GUARDIAN_LABEL.search(label) else "payee" if _PAYEE_LABEL.search(label)
                    else "staff" if _STAFF_LABEL.search(label) else "subject")
            if kind == "person":
                add("person", role, name, name, offset, end, 0.9)
            elif kind == "organisation" and role == "payee":
                add("organisation", "payee", name, name, offset, end, 0.9)
            elif kind is None and role == "subject":
                single = re.match(r"^[A-Z][a-z]+$", value.strip())
                if single:
                    add("person", role, value.strip(), value.strip(), offset, end, 0.6)
        elif _SERVICE_LABEL.search(label):
            add("service", "service", value, value, offset, end, 0.85)
        elif _ORG_LABEL.search(label):
            role = "addressee" if re.search(r"buyer|client|customer|^to$|kind attn|m/s|bill to|consignee", label) \
                else "named"
            for name, start, finish in find_orgs(value)[:1]:
                add("organisation", role, name, name, offset + start, offset + finish, 0.9)
        elif _MONEY_LABEL.search(label) and not dates and not re.search(r"\bno\b|\bnumber\b|\bdate\b", label):
            if any(start <= offset < finish or offset <= start < end for start, finish in marked_spans):
                continue
            parsed = parse_amount_field(value.split("(")[0])
            role = amount_role(label)
            if parsed.valid and role in ("balance", "paid", "covered", "total"):
                add("amount", role, value, parsed.value, offset, end, 0.8)
                amount_offsets.add(offset)
            elif parsed.issue == "FOREIGN_CURRENCY":
                add("amount", "foreign", value, None, offset, end, 0.0)

    # --- unmarked amounts closing a table row ("Interim bill amount 4,37,000") -----
    for match in _MONEY_ROW.finditer(text):
        start, end = match.span("amount")
        label = match.group("label")
        if (start in amount_offsets or any(a < end and start < b for a, b in marked_spans)
                or not _MONEY_ROW_LABEL.search(label) or _COUNT_NOUNS.search(label)):
            continue
        parsed = parse_amount_field(match.group("amount").split("(")[0])
        role = amount_role(label)
        if parsed.valid and role in ("balance", "paid", "covered", "total"):
            add("amount", role, match.group("amount"), parsed.value, start, end, 0.75)

    # --- dates ------------------------------------------------------------------
    for value, start, end, raw in find_dates(flat):
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        line = text[line_start:line_end if line_end != -1 else len(text)]
        context = flat[max(line_start if len(line) < 72 else start - 70, start - 70, 0):start]
        role = _date_role(context, line.strip() == raw.strip())
        if role == "other" and text.count("\n", 0, start) < 6:
            role = "issue"                      # an unlabelled date in the document header
        add("date", role, raw, value.isoformat(), start, end, 0.9)

    # --- identifiers ------------------------------------------------------------
    taken = []
    for family, pattern in _INLINE_ID_RES:
        for match in pattern.finditer(flat):
            start, end = match.span(1)
            raw = match.group(1).rstrip("-/.")
            if any(start < b and a < end for a, b in taken) or len(normalize_id(raw)) < 4 or find_dates(raw):
                continue
            taken.append((start, end))
            add("identifier", family, raw, normalize_id(raw), start, end, 0.85)
    for match in _DOC_REF.finditer(flat):
        start, end = match.span(1)
        if not any(start < b and a < end for a, b in taken) and not find_dates(match.group(1)):
            add("identifier", "document_reference", match.group(1), normalize_id(match.group(1)), start, end, 0.7)
    for match in _UPI.finditer(flat):
        add("identifier", "upi", match.group(0), match.group(0).casefold(), match.start(), match.end(), 0.9)

    # --- organisations ------------------------------------------------------------
    seen_orgs = {(f.source.excerpt, f.value) for f in fields if f.kind == "organisation"}
    for name, start, end in find_orgs(text):
        key = (locator.ref(start, end).excerpt, name)
        if key not in seen_orgs:
            add("organisation", "mention", name, name, start, end, 0.75)

    # --- people in prose ------------------------------------------------------------
    known = {(f.value, f.role) for f in fields if f.kind == "person"}

    def add_person(role, name, start, confidence):
        if (name, role) not in known:
            known.add((name, role))
            add("person", role, name, name, start, start + len(name), confidence)

    for role, confidence, anchor in _PROSE_PERSON_ANCHORS:
        for match in anchor.finditer(text):
            kind, name, _ = take_entity(text[match.end():match.end() + 120])
            if kind == "person" and (len(name.split()) >= 2 or role == "subject" and confidence >= 0.8):
                add_person(role, name, match.end(), confidence)
            elif kind == "organisation" and role == "payee":
                add("organisation", "payee", name, name, match.end(), match.end() + len(name), 0.85)
            elif kind == "organisation" and role == "subject" and confidence >= 0.85:
                add("organisation", "named", name, name, match.end(), match.end() + len(name), 0.85)
    if not is_campaign:
        position = 0
        for line in text.split("\n"):
            kind, name, used = take_entity(line)
            rest = flat[position + used:position + used + 260]
            if kind == "person" and len(name.split()) >= 2 and re.match(r"\s*(?:,|\()", rest) \
                    and _SUBJECT_VERBS.search(rest):
                add_person("subject", name, position, 0.8)
            position += len(line) + 1
    for match in re.finditer(r"\bDr\.?[ \t]+", text):
        kind, name, _ = take_entity(text[match.end():match.end() + 80])
        if kind == "person":
            add_person("staff", name, match.end(), 0.8)

    # --- service descriptions in prose ---------------------------------------------
    for anchor in _PROSE_SERVICE_ANCHORS:
        for match in anchor.finditer(flat):
            start, end = match.span(1)
            line_end = text.find("\n", start)
            line_start = text.rfind("\n", 0, start) + 1
            if line_end != -1 and line_end < end and line_end - line_start < 72:
                end = line_end                  # a form/table line ends the description
            value = re.split(r"\s{3,}", text[start:end])[0]
            value = " ".join(value.split()).strip(" .;:,")
            if 3 <= len(value) <= 160:
                add("service", "service", value, value, start, start + len(value), 0.7)
    return fields


def _issuer(text: str) -> Optional[str]:
    """The organisation on the letterhead: an organisation in the first lines."""
    lines = [line.strip() for line in text.split("\n") if line.strip() and not line.strip().startswith("[Page")]
    for line in lines[:2]:
        if re.match(r"^(?:from|to|subject|sent|date|ref)\b\s*:", line, re.I):
            continue
        orgs = find_orgs(line)
        if orgs:
            return orgs[0][0]
    return None


def extract_document(index: int, document: DocumentInput) -> DocumentEvidence:
    text = document.text or ""
    evidence = DocumentEvidence(index=index, title=document.title, doc_type=document.doc_type)
    words = re.findall(r"[A-Za-z]{3,}", text)
    controls = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\r\t")
    if document.load_error:
        evidence.readable = False
        evidence.issues.append(f"LOAD_ERROR:{document.load_error}")
        return evidence
    if (len(words) < 5 or controls > 0.02 * max(len(text), 1)
            or re.fullmatch(r"\s*\[?(unreadable|illegible)\]?\s*", text, re.I)):
        evidence.readable = False
        evidence.issues.append("UNREADABLE")
        return evidence
    locator = Locator(text, document.title, index)
    evidence.fields = _extract_fields(text, locator, is_campaign=False)
    evidence.issuer = _issuer(text)
    evidence.issuer_kind = org_kind(evidence.issuer) if evidence.issuer else None
    head = f"{document.doc_type.replace('_', ' ')} {document.title} {text}"
    has_amount = any(f.role in ("total", "balance") and f.value is not None for f in evidence.of("amount"))
    for name, pattern in _EVIDENCE_RES.items():
        if pattern.search(head):
            if name == "cost":
                continue            # decided from the amounts below, not from title words
            if name == "clinical" and len(set(m.group(0).casefold() for m in pattern.finditer(text))) < 2:
                continue
            if name == "org_identity" and not evidence.of("identifier", "registration_no"):
                continue
            if name in ("org_identity", "authorization") and evidence.issuer_kind == "vendor":
                continue                        # a supplier quoting the buyer's number is not proof
            evidence.evidence_classes.append(name)
    if has_amount:
        evidence.evidence_classes.insert(0, "cost")
    evidence.traceability = sum([
        bool(evidence.issuer),
        bool(evidence.of("date")),
        bool(evidence.of("identifier")),
        bool(_SIGNATORY.search(text) or evidence.of("person", "staff")),
    ])
    if any(f.role == "invalid" for f in evidence.of("amount")):
        evidence.issues.append("MALFORMED_AMOUNT")
    if any(f.role == "foreign" for f in evidence.of("amount")):
        evidence.issues.append("FOREIGN_CURRENCY_AMOUNT")
    return evidence


def extract_claim(case: CaseInput) -> DocumentEvidence:
    """Structured view of what the campaign itself asserts (title + story)."""
    text = f"{case.title}\n\n{case.story}"
    claim = DocumentEvidence(index=-1, title=CAMPAIGN_TEXT, doc_type="CAMPAIGN")
    claim.fields = _extract_fields(text, Locator(text, CAMPAIGN_TEXT, -1), is_campaign=True)
    return claim
