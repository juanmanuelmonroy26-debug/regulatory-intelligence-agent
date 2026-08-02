# Regulatory Intelligence Agent

## Objetivo

Construir un agente autónomo que monitoree diariamente fuentes regulatorias oficiales de la DIAN relacionadas con facturación electrónica, detecte cambios reales, clasifique su impacto funcional para Alegra, interprete las implicaciones regulatorias mediante IA y notifique automáticamente al equipo de Product Regulation.

---

# Flujo general

GitHub Actions (cada día)

↓

Monitor DIAN

↓

Snapshot

↓

Comparación

↓

Clasificación de impacto

↓

IA interpreta

↓

Reporte (.docx)

---

# Responsabilidades

## 1. Monitor

Responsabilidad única:

Consultar las fuentes oficiales de la DIAN.

No interpreta.

No compara.

No clasifica.

Solo descarga.

---

## 2. Snapshot Manager

Guardar una copia estructurada de la fuente.

Debe incluir:

- fecha
- fuente
- contenido
- hash

---

## 3. Comparator

Compara el snapshot nuevo contra el anterior.

Debe detectar:

- normas nuevas
- normas eliminadas
- modificaciones

No interpreta.

Solo detecta diferencias.

---

## 4. Functional Impact Classifier

No clasifica por tipo jurídico.

Clasifica por impacto funcional sobre el producto.

Categorías:

- Facturación electrónica
- Documento soporte
- Nómina electrónica
- RADIAN
- Eventos
- Validaciones
- Catálogos
- Sujetos obligados
- Calendarios
- Firma electrónica
- API
- XML
- Reglas de validación

Debe asignar:

- prioridad
- módulo afectado
- equipo potencialmente impactado

---

## 5. Interpreter

Recibe únicamente los cambios detectados.

Debe responder:

- Qué cambió.
- Qué implica.
- Qué módulo afecta.
- Qué tan urgente es.
- Qué debería revisar Producto.
- Qué debería revisar Ingeniería.
- Qué debería revisar Customer Success.

Nunca inventar regulación.

Siempre trabajar únicamente con el texto oficial recibido.

---

## 6. Reporter

Generar un documento Word (.docx) con todos los cambios del día.

Debe incluir por cada cambio:

- Norma identificada
- Tipo de cambio
- Categoría funcional
- Prioridad
- Resumen interpretado
- Acciones sugeridas por equipo

---

# Fuentes regulatorias

## Lector 1

https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/normatividad/

Frecuencia:

Diaria

---

## Lector 2

https://normograma.dian.gov.co/dian/compilacion/t_1_normativa_tributaria.html?q=TRIBUTARIO

Monitorear únicamente el ítem 1.6 — Sistema de Facturación Electrónica.

Frecuencia:

Semanal

---

## Lector 3

https://www.dian.gov.co/normatividad/Paginas/ProyectosNormas.aspx

Monitorear proyectos de normas publicados por la DIAN.

Frecuencia:

Diaria

---

# Principios

- Cada módulo debe tener una única responsabilidad.
- El pipeline debe ser reutilizable.
- La IA nunca hace scraping.
- La IA nunca inventa regulación.
- Python realiza toda la adquisición y comparación.
- La IA únicamente interpreta.
- Toda decisión debe quedar registrada para auditoría.
