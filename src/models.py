from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class SourceID(str, Enum):
    MICROSITIOS = "micrositios"
    NORMOGRAMA = "normograma"
    PROYECTOS_NORMAS = "proyectos_normas"


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class FunctionalCategory(str, Enum):
    FACTURACION_ELECTRONICA = "Facturación electrónica"
    DOCUMENTO_SOPORTE = "Documento soporte"
    NOMINA_ELECTRONICA = "Nómina electrónica"
    RADIAN = "RADIAN"
    EVENTOS = "Eventos"
    VALIDACIONES = "Validaciones"
    CATALOGOS = "Catálogos"
    SUJETOS_OBLIGADOS = "Sujetos obligados"
    CALENDARIOS = "Calendarios"
    FIRMA_ELECTRONICA = "Firma electrónica"
    API = "API"
    XML = "XML"
    REGLAS_VALIDACION = "Reglas de validación"
    GENERAL = "General"


class Priority(str, Enum):
    HIGH = "Alta"
    MEDIUM = "Media"
    LOW = "Baja"


class Team(str, Enum):
    PRODUCT = "Producto"
    ENGINEERING = "Ingeniería"
    CUSTOMER_SUCCESS = "Customer Success"


# ── Module 1 output ───────────────────────────────────────────────────────────

class RawFetch(BaseModel):
    source_id: SourceID
    url: str
    fetched_at: datetime
    html: str
    http_status: int


# ── Module 2 — Snapshot ───────────────────────────────────────────────────────

class NormItem(BaseModel):
    norm_id: str
    title: str
    url: str | None = None
    raw_text: str


class Snapshot(BaseModel):
    source_id: SourceID
    url: str
    snapshot_date: datetime
    content_hash: str
    norms: list[NormItem]
    raw_text_full: str


# ── Module 3 — Comparator ─────────────────────────────────────────────────────

class NormDiff(BaseModel):
    change_type: ChangeType
    norm_id: str
    previous: NormItem | None = None
    current: NormItem | None = None


class ComparisonResult(BaseModel):
    source_id: SourceID
    compared_at: datetime
    previous_date: datetime | None
    current_date: datetime
    hash_changed: bool
    diffs: list[NormDiff]
    previous_hash: str | None
    current_hash: str


# ── Module 4 — Classifier ─────────────────────────────────────────────────────

class ClassifiedChange(BaseModel):
    diff: NormDiff
    category: FunctionalCategory
    priority: Priority
    affected_teams: list[Team]
    classification_rationale: str


# ── Module 5 — Interpreter ────────────────────────────────────────────────────

class InterpretedChange(BaseModel):
    classified: ClassifiedChange
    what_changed: str
    implications: str
    affected_module: str
    urgency: Priority
    product_action: str
    engineering_action: str
    cs_action: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int


# ── Audit log entry ───────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    run_id: str
    timestamp: datetime
    source_id: SourceID
    stage: str
    status: Literal["ok", "error", "skipped"]
    detail: str
