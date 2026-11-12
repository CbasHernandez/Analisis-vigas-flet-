"""Generación de la memoria de cálculo en Word con docxtpl."""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

from docx.shared import Cm
from docxtpl import DocxTemplate, InlineImage

from app.graficas import figura_a_png, figura_diagramas
from app.modelo import DatosViga, Resultado, analizar, tabla_estaciones, verificar

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "plantillas" / "memoria.docx"
CARPETA_SALIDAS = RAIZ / "salidas"
# Autores que aparecen en la portada de la memoria. Agregue aquí a su compañero/a: "Nombre (código)".
AUTORES = ["Sebastián Hernández (20231579036)"]


def _fila(nombre: str, valor, unidad: str) -> dict:
    return {"nombre": nombre, "valor": valor, "unidad": unidad}


def construir_contexto(d: DatosViga, r: Resultado, proyecto: str, nombre: str,
                       descripcion: str = "") -> dict:
    """Arma el diccionario de variables que la plantilla Jinja reemplaza."""
    ver = verificar(d, r)
    if "R_kN" in r.reacciones:
        reac = [_fila("Reacción vertical R", f"{r.reacciones['R_kN']:.3f}", "kN"),
                _fila("Momento de empotramiento M₀", f"{r.reacciones['M_empotramiento_kNm']:.3f}", "kN·m")]
    else:
        reac = [_fila("Reacción en A (x = 0)", f"{r.reacciones['R_A_kN']:.3f}", "kN"),
                _fila("Reacción en B (x = L)", f"{r.reacciones['R_B_kN']:.3f}", "kN")]
    principales = reac + [
        _fila("Cortante máximo |V|max", f"{r.V_max_kN:.3f}", "kN"),
        _fila(f"Momento máximo |M|max (en x = {r.x_M_max_m:.3f} m)", f"{r.M_max_kNm:.3f}", "kN·m"),
        _fila("Esfuerzo máximo σmax", f"{r.sigma_max_MPa:.3f}", "MPa"),
        _fila(f"Deflexión máxima δmax (en x = {r.x_delta_max_m:.3f} m)", f"{r.delta_max_mm:.3f}", "mm"),
        _fila("Deflexión admisible δadm = L/n", f"{r.flecha_adm_mm:.3f}", "mm")]
    estado = lambda ok: "CUMPLE" if ok else "NO CUMPLE"  # noqa: E731
    verificaciones = [
        {"nombre": "Equilibrio vertical: |Σcargas − ΣR|", "valor": f"{ver['error_fuerzas_kN']:.2e} kN",
         "estado": estado(ver["error_fuerzas_kN"] < 1e-6)},
        {"nombre": "Momento en x = L (debe ser 0)", "valor": f"{ver['momento_en_L_kNm']:.2e} kN·m",
         "estado": estado(ver["momento_en_L_kNm"] < 1e-6)},
        {"nombre": f"Convergencia de malla (δmax con {2 * d.n_puntos - 1} pts)",
         "valor": f"variación {ver['variacion_malla'] * 100:.4f} %", "estado": estado(ver["variacion_malla"] < 1e-3)}]
    return {
        "proyecto": proyecto, "nombre_calculo": nombre, "autores": "; ".join(AUTORES), "descripcion": descripcion or "—",
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "apoyo_texto": "simple (articulado–rodillo)" if d.apoyo == "simple" else "en voladizo (empotrado–libre)",
        "L": f"{d.longitud_m:g}", "n_puntos": d.n_puntos,
        "I": f"{r.I_m4:.4e}", "S": f"{r.S_m3:.4e}", "EI": f"{r.EI_kNm2:,.1f}",
        "datos_entrada": [
            _fila("Longitud L", f"{d.longitud_m:g}", "m"), _fila("Módulo de elasticidad E", f"{d.E_GPa:g}", "GPa"),
            _fila("Base b", f"{d.b_cm:g}", "cm"), _fila("Altura h", f"{d.h_cm:g}", "cm"),
            _fila("Esfuerzo admisible σadm", f"{d.sigma_adm_MPa:g}", "MPa"),
            _fila("Límite de flecha n (δadm = L/n)", f"{d.limite_flecha:g}", "—")],
        "cargas_puntuales": [{"n": i, "x": f"{c.posicion_m:g}", "P": f"{c.P_kN:g}"}
                             for i, c in enumerate(d.puntuales, 1)] or [{"n": "—", "x": "—", "P": "—"}],
        "cargas_distribuidas": [{"n": i, "x_ini": f"{c.x_ini_m:g}", "x_fin": f"{c.x_fin_m:g}", "w": f"{c.w_kN_m:g}"}
                                for i, c in enumerate(d.distribuidas, 1)] or
                               [{"n": "—", "x_ini": "—", "x_fin": "—", "w": "—"}],
        "resultados_principales": principales,
        "estaciones": tabla_estaciones(r, 11),
        "verificaciones": verificaciones,
        "conclusion_esfuerzo": (f"Esfuerzo: σmax = {r.sigma_max_MPa:.2f} MPa "
                                f"{'≤' if r.cumple_esfuerzo else '>'} σadm = {d.sigma_adm_MPa:g} MPa → "
                                f"{estado(r.cumple_esfuerzo)}."),
        "conclusion_flecha": (f"Flecha: δmax = {r.delta_max_mm:.2f} mm "
                              f"{'≤' if r.cumple_flecha else '>'} δadm = L/{d.limite_flecha:g} = "
                              f"{r.flecha_adm_mm:.2f} mm → {estado(r.cumple_flecha)}."),
        "dictamen": "LA VIGA CUMPLE" if r.cumple else "LA VIGA NO CUMPLE (revisar sección o cargas)",
    }


def _nombre_archivo(proyecto: str, nombre: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{proyecto}_{nombre}").strip("_")
    return f"memoria_{base}_{datetime.now():%Y%m%d_%H%M%S}.docx"


def generar_memoria(calculo: dict, carpeta: Path | str = CARPETA_SALIDAS) -> Path:
    """Genera la memoria .docx de un cálculo guardado (dict devuelto por BaseDatos.obtener_calculo)."""
    d = DatosViga.desde_dict(calculo["datos"])
    r = analizar(d)
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)

    plantilla = DocxTemplate(PLANTILLA)
    png = figura_a_png(figura_diagramas(d, r))                 # misma figura que se ve en la interfaz
    contexto = construir_contexto(d, r, calculo["proyecto"], calculo["nombre"],
                                  calculo.get("proyecto_descripcion", ""))
    contexto["grafica"] = InlineImage(plantilla, io.BytesIO(png), width=Cm(14))
    plantilla.render(contexto)
    destino = carpeta / _nombre_archivo(calculo["proyecto"], calculo["nombre"])
    plantilla.save(destino)
    return destino
