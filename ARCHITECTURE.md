# Regulatory Intelligence Agent

## Objetivo

Construir un agente autónomo que monitoree diariamente fuentes regulatorias oficiales de la DIAN relacionadas con facturación electrónica, detecte cambios reales, clasifique su impacto funcional para Alegra, interprete las implicaciones regulatorias mediante Claude AI y notifique automáticamente al equipo de Product Regulation.

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

Claude interpreta

↓

Slack

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

## 5. Claude Interpreter

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

## 6. Slack Notifier

Enviar un mensaje estructurado.

Ejemplo:

Fuente:

DIAN

Cambio detectado

Resolución XXXXX

Impacto

Alta

Módulo

Facturación Electrónica

Resumen

...

Acción sugerida

...

---

# Fuentes regulatorias

## Lector 1

https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/normatividad/

Frecuencia:

Diaria

---

## Lector 2

https://normograma.dian.gov.co/dian/compilacion/t_1_normativa_tributaria.html

Monitorear únicamente la parte correspondiente al Sistema de Facturación.

Frecuencia:

Semanal

---

# Principios

- Cada módulo debe tener una única responsabilidad.
- El pipeline debe ser reutilizable.
- Claude nunca hace scraping.
- Claude nunca inventa regulación.
- Python realiza toda la adquisición y comparación.
- Claude únicamente interpreta.
- Toda decisión debe quedar registrada para auditoría.# Regulatory Intelligence Agent

## Objetivo

Construir un agente autónomo que monitoree diariamente fuentes regulatorias oficiales de la DIAN relacionadas con facturación electrónica, detecte cambios reales, clasifique su impacto funcional para Alegra, interprete las implicaciones regulatorias mediante Claude AI y notifique automáticamente al equipo de Product Regulation.

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

Claude interpreta

↓

Slack

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

## 5. Claude Interpreter

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

## 6. Slack Notifier

Enviar un mensaje estructurado.

Ejemplo:

Fuente:

DIAN

Cambio detectado

Resolución XXXXX

Impacto

Alta

Módulo

Facturación Electrónica

Resumen

...

Acción sugerida

...

---

# Fuentes regulatorias

## Lector 1

https://micrositios.dian.gov.co/sistema-de-facturacion-electronica/normatividad/

Frecuencia:

Diaria

---

## Lector 2

https://normograma.dian.gov.co/dian/compilacion/t_1_normativa_tributaria.html

Monitorear únicamente la parte correspondiente al Sistema de Facturación.

Frecuencia:

Semanal

---

# Principios

- Cada módulo debe tener una única responsabilidad.
- El pipeline debe ser reutilizable.
- Claude nunca hace scraping.
- Claude nunca inventa regulación.
- Python realiza toda la adquisición y comparación.
- Claude únicamente interpreta.
- Toda decisión debe quedar registrada para auditoría.clau