from __future__ import annotations

import logging

from src.models import ChangeType, ClassifiedChange, FunctionalCategory, NormDiff, Priority, Team

logger = logging.getLogger(__name__)

_RULES: list[dict] = [
    {
        "keywords": ["nómina", "nomina", "nómina electrónica", "nomina electronica"],
        "category": FunctionalCategory.NOMINA_ELECTRONICA,
        "priority": Priority.HIGH,
        "teams": [Team.PRODUCT, Team.ENGINEERING],
    },
    {
        "keywords": ["radian", "endoso", "mandato", "circulación electrónica"],
        "category": FunctionalCategory.RADIAN,
        "priority": Priority.HIGH,
        "teams": [Team.PRODUCT, Team.ENGINEERING],
    },
    {
        "keywords": ["documento soporte", "documento equivalente"],
        "category": FunctionalCategory.DOCUMENTO_SOPORTE,
        "priority": Priority.HIGH,
        "teams": [Team.PRODUCT, Team.ENGINEERING],
    },
    {
        "keywords": ["firma", "certificado digital", "token criptográfico", "certificado electrónico"],
        "category": FunctionalCategory.FIRMA_ELECTRONICA,
        "priority": Priority.HIGH,
        "teams": [Team.ENGINEERING],
    },
    {
        "keywords": ["xml", "ubl", "esquema xsd", ".xsd", "anexo técnico"],
        "category": FunctionalCategory.XML,
        "priority": Priority.HIGH,
        "teams": [Team.ENGINEERING],
    },
    {
        "keywords": ["api", "web service", "servicio web", "webservice", "servicio electrónico"],
        "category": FunctionalCategory.API,
        "priority": Priority.HIGH,
        "teams": [Team.ENGINEERING],
    },
    {
        "keywords": ["catálogo", "catalogo", "tabla de códigos", "código de"],
        "category": FunctionalCategory.CATALOGOS,
        "priority": Priority.MEDIUM,
        "teams": [Team.ENGINEERING],
    },
    {
        "keywords": ["evento", "acuse de recibo", "recibo del bien", "rechazo", "aceptación expresa"],
        "category": FunctionalCategory.EVENTOS,
        "priority": Priority.MEDIUM,
        "teams": [Team.PRODUCT, Team.ENGINEERING],
    },
    {
        "keywords": ["validación", "validacion", "reglas de validación", "regla de validación"],
        "category": FunctionalCategory.REGLAS_VALIDACION,
        "priority": Priority.HIGH,
        "teams": [Team.ENGINEERING],
    },
    {
        "keywords": ["calendario", "plazo", "fecha límite", "fecha de vencimiento", "implementación obligatoria"],
        "category": FunctionalCategory.CALENDARIOS,
        "priority": Priority.MEDIUM,
        "teams": [Team.PRODUCT, Team.CUSTOMER_SUCCESS],
    },
    {
        "keywords": ["sujeto obligado", "obligado a facturar", "contribuyente obligado"],
        "category": FunctionalCategory.SUJETOS_OBLIGADOS,
        "priority": Priority.MEDIUM,
        "teams": [Team.PRODUCT, Team.CUSTOMER_SUCCESS],
    },
    {
        "keywords": ["factura", "facturación", "facturacion", "factura electrónica", "fe "],
        "category": FunctionalCategory.FACTURACION_ELECTRONICA,
        "priority": Priority.HIGH,
        "teams": [Team.PRODUCT, Team.ENGINEERING, Team.CUSTOMER_SUCCESS],
    },
]

_FALLBACK_CATEGORY = FunctionalCategory.GENERAL
_FALLBACK_PRIORITY = Priority.LOW
_FALLBACK_TEAMS = [Team.PRODUCT]


class ImpactClassifier:
    def classify(self, diff: NormDiff) -> ClassifiedChange:
        norm = diff.current or diff.previous
        search_text = f"{diff.norm_id} {norm.raw_text if norm else ''}".lower()

        matched_rule: dict | None = None
        matched_keyword: str | None = None

        for rule in _RULES:
            for kw in rule["keywords"]:
                if kw in search_text:
                    matched_rule = rule
                    matched_keyword = kw
                    break
            if matched_rule:
                break

        if matched_rule:
            category = matched_rule["category"]
            priority = matched_rule["priority"]
            teams = matched_rule["teams"]
            rationale = f"Keyword match: '{matched_keyword}'"
        else:
            category = _FALLBACK_CATEGORY
            priority = _FALLBACK_PRIORITY
            teams = _FALLBACK_TEAMS
            rationale = "No keyword matched — fallback to General"

        if diff.change_type == ChangeType.REMOVED and priority != Priority.HIGH:
            priority = Priority.HIGH
            rationale += " [escalated: norm REMOVED]"

        logger.info(f"Classified '{diff.norm_id}' → {category} / {priority} ({rationale})")
        return ClassifiedChange(
            diff=diff,
            category=category,
            priority=priority,
            affected_teams=teams,
            classification_rationale=rationale,
        )

    def classify_all(self, diffs: list[NormDiff]) -> list[ClassifiedChange]:
        return [self.classify(d) for d in diffs]
