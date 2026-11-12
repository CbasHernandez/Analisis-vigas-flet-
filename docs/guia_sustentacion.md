# Guía rápida para la sustentación (10 min + 5 min de preguntas)

## Recorrido sugerido de la demostración
1. (1 min) Problema: diagramas y deflexión de vigas, hoy hechos a mano o en Excel.
2. (3 min) App: caso por defecto → Calcular → leer R, Mmax, σ, δ y banner → mostrar un campo vacío (validación) → Guardar.
3. (2 min) Historial: buscar, abrir, **generar memoria .docx** y mostrar tabla + gráfica; eliminar con confirmación.
4. (3 min) Código: `modelo.py` (qué hace cada función), `db.py` (esquema y consultas con `?`), flujo de datos.

## Dónde está cada cosa
| Pregunta típica | Archivo / función |
|---|---|
| ¿Dónde se calcula V y M sin ciclos? | `modelo.cortante_y_momento` (broadcasting `x[:, None]` vs. arreglos de cargas) |
| ¿Cómo se usa SciPy? | `modelo.deflexion` → `cumulative_trapezoid` dos veces |
| ¿Cómo se imponen las condiciones de borde? | `modelo.deflexion` (voladizo: sin constantes; simple: `C1 = -y0(L)/L`) |
| ¿Cómo se valida? | `modelo.validar` (lógica) y `ui/tema.leer_numero` (texto → número) |
| ¿Qué pasa al guardar? | `VistaCalculo.guardar` → `BaseDatos.guardar_calculo` (JSON de entradas + resumen) |
| ¿Cómo se reabre un cálculo? | `VistaHistorial.abrir` → `VistaCalculo.cargar` (recalcula desde el JSON) |
| ¿Cómo se arma el Word? | `reporte.construir_contexto` + `generar_memoria` (`InlineImage`) y `plantillas/memoria.docx` |
| ¿Por qué `ON DELETE CASCADE`? | Al borrar un proyecto se borran sus cálculos (`PRAGMA foreign_keys = ON`) |

## Cómo verificar a mano (para explicar)
Viga simple, w = 10 kN/m, L = 6 m, 30×50 cm, E = 21 GPa: `I = 0.3·0.5³/12 = 3.125×10⁻³ m⁴`, `EI = 65 625 kN·m²`, `Mmax = wL²/8 = 45 kN·m`, `σ = 45/0.0125 = 3.6 MPa`, `δ = 5wL⁴/(384EI) = 2.571 mm`.

## Modificaciones pequeñas que podría pedir el docente
- Cambiar el límite de flecha por defecto (`vista_calculo.py`, campo `f_limite`).
- Agregar un campo o resultado nuevo (p. ej. giro máximo: `r.theta` ya existe en `Resultado`).
- Cambiar el número de estaciones de la tabla Word (`tabla_estaciones(r, 11)` en `reporte.py`).
- Cambiar el color o el título de una gráfica (`graficas.py`).
