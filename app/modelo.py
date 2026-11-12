"""Modelo de ingeniería: análisis de vigas isostáticas (sin dependencias de Flet).

Calcula reacciones, fuerza cortante V(x), momento flector M(x), pendiente θ(x)
y deflexión δ(x) de una viga prismática sometida a cargas puntuales y
distribuidas rectangulares, más los chequeos de esfuerzo y flecha admisible.

Tipos de apoyo:
    "simple"   -> apoyo articulado en x=0 y rodillo en x=L.
    "voladizo" -> empotrada en x=0 y libre en x=L.

Convenciones (Hibbeler, Mecánica de materiales; Gere & Goodno):
    * Cargas hacia abajo = positivas. Reacciones hacia arriba = positivas.
    * M positivo = tracción en la fibra inferior (la viga "sonríe").
    * V(x) = dM/dx. Ecuación de la elástica: EI·y'' = M, con y positivo hacia
      arriba. Se reporta δ = -y (positivo hacia abajo).

Unidades: L [m], P [kN], w [kN/m], V [kN], M [kN·m], E [GPa], b y h [cm],
I [m⁴], EI [kN·m²], θ [rad], δ [mm], σ [MPa].
Equivalencia usada: 1 GPa = 1e6 kN/m².
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import cumulative_trapezoid

GPA_A_KN_M2 = 1.0e6      # 1 GPa = 1e6 kN/m²
KPA_A_MPA = 1.0e-3       # 1 kPa = 1e-3 MPa
APOYOS = ("simple", "voladizo")


class ErrorDeEntrada(ValueError):
    """Se lanza cuando los datos ingresados no son válidos."""


@dataclass
class CargaPuntual:
    posicion_m: float
    P_kN: float


@dataclass
class CargaDistribuida:
    x_ini_m: float
    x_fin_m: float
    w_kN_m: float


@dataclass
class DatosViga:
    longitud_m: float
    apoyo: str
    E_GPa: float
    b_cm: float
    h_cm: float
    sigma_adm_MPa: float
    limite_flecha: float                      # la flecha admisible es L / limite_flecha
    puntuales: list[CargaPuntual] = field(default_factory=list)
    distribuidas: list[CargaDistribuida] = field(default_factory=list)
    n_puntos: int = 1001

    def a_dict(self) -> dict:
        """Serializa los datos (para guardarlos como JSON en SQLite)."""
        return {
            "longitud_m": self.longitud_m, "apoyo": self.apoyo, "E_GPa": self.E_GPa,
            "b_cm": self.b_cm, "h_cm": self.h_cm, "sigma_adm_MPa": self.sigma_adm_MPa,
            "limite_flecha": self.limite_flecha, "n_puntos": self.n_puntos,
            "puntuales": [vars(c).copy() for c in self.puntuales],
            "distribuidas": [vars(c).copy() for c in self.distribuidas],
        }

    @classmethod
    def desde_dict(cls, d: dict) -> "DatosViga":
        """Reconstruye los datos desde un diccionario (inverso de a_dict)."""
        return cls(
            longitud_m=d["longitud_m"], apoyo=d["apoyo"], E_GPa=d["E_GPa"],
            b_cm=d["b_cm"], h_cm=d["h_cm"], sigma_adm_MPa=d["sigma_adm_MPa"],
            limite_flecha=d["limite_flecha"], n_puntos=d.get("n_puntos", 1001),
            puntuales=[CargaPuntual(**c) for c in d.get("puntuales", [])],
            distribuidas=[CargaDistribuida(**c) for c in d.get("distribuidas", [])],
        )


@dataclass
class Resultado:
    x: np.ndarray            # [m]
    V: np.ndarray            # [kN]
    M: np.ndarray            # [kN·m]
    theta: np.ndarray        # [rad]
    delta: np.ndarray        # [mm], positivo hacia abajo
    reacciones: dict         # {"R_A_kN","R_B_kN"} (simple) o {"R_kN","M_empotramiento_kNm"} (voladizo)
    I_m4: float
    S_m3: float
    EI_kNm2: float
    M_max_kNm: float         # máximo valor absoluto
    x_M_max_m: float
    V_max_kN: float          # máximo valor absoluto
    delta_max_mm: float      # máximo valor absoluto
    x_delta_max_m: float
    sigma_max_MPa: float
    flecha_adm_mm: float
    cumple_esfuerzo: bool
    cumple_flecha: bool
    error_equilibrio_kNm: float

    @property
    def cumple(self) -> bool:
        return self.cumple_esfuerzo and self.cumple_flecha


# ----------------------------------------------------------------------------
# Validación
# ----------------------------------------------------------------------------
def _es_numero(v) -> bool:
    return isinstance(v, (int, float, np.floating)) and np.isfinite(v)


def validar(d: DatosViga) -> None:
    """Revisa los datos y lanza ErrorDeEntrada con un mensaje claro si hay un problema."""
    escalares = {"Longitud": d.longitud_m, "E": d.E_GPa, "Base b": d.b_cm, "Altura h": d.h_cm,
                 "Esfuerzo admisible": d.sigma_adm_MPa, "Límite de flecha": d.limite_flecha}
    for nombre, valor in escalares.items():
        if not _es_numero(valor) or valor <= 0:
            raise ErrorDeEntrada(f"{nombre} debe ser un número mayor que cero.")
    if d.apoyo not in APOYOS:
        raise ErrorDeEntrada(f"Tipo de apoyo no válido: {d.apoyo!r}.")
    if not isinstance(d.n_puntos, int) or not 101 <= d.n_puntos <= 20001:
        raise ErrorDeEntrada("El número de puntos de evaluación debe estar entre 101 y 20001.")
    if not d.puntuales and not d.distribuidas:
        raise ErrorDeEntrada("Agregue al menos una carga (puntual o distribuida).")
    L = d.longitud_m
    for i, c in enumerate(d.puntuales, 1):
        if not _es_numero(c.P_kN) or c.P_kN == 0:
            raise ErrorDeEntrada(f"Carga puntual {i}: P debe ser un número distinto de cero.")
        if not _es_numero(c.posicion_m) or not 0 <= c.posicion_m <= L:
            raise ErrorDeEntrada(f"Carga puntual {i}: la posición debe estar entre 0 y L = {L:g} m.")
    for i, c in enumerate(d.distribuidas, 1):
        if not _es_numero(c.w_kN_m) or c.w_kN_m == 0:
            raise ErrorDeEntrada(f"Carga distribuida {i}: w debe ser un número distinto de cero.")
        if not (_es_numero(c.x_ini_m) and _es_numero(c.x_fin_m)) or not 0 <= c.x_ini_m < c.x_fin_m <= L:
            raise ErrorDeEntrada(f"Carga distribuida {i}: se requiere 0 ≤ x_ini < x_fin ≤ L = {L:g} m.")


# ----------------------------------------------------------------------------
# Propiedades y estática
# ----------------------------------------------------------------------------
def propiedades_seccion(b_cm: float, h_cm: float) -> tuple[float, float]:
    """Sección rectangular: I = b·h³/12 [m⁴] y S = b·h²/6 [m³]."""
    b, h = b_cm / 100.0, h_cm / 100.0
    return b * h**3 / 12.0, b * h**2 / 6.0


def _arreglos_cargas(d: DatosViga):
    """Convierte las listas de cargas en arreglos NumPy (a, P) y (a, b, w)."""
    a_p = np.array([c.posicion_m for c in d.puntuales], dtype=float)
    P = np.array([c.P_kN for c in d.puntuales], dtype=float)
    a_d = np.array([c.x_ini_m for c in d.distribuidas], dtype=float)
    b_d = np.array([c.x_fin_m for c in d.distribuidas], dtype=float)
    w = np.array([c.w_kN_m for c in d.distribuidas], dtype=float)
    return a_p, P, a_d, b_d, w


def reacciones(d: DatosViga) -> dict:
    """Reacciones por equilibrio estático (ΣFy = 0, ΣM = 0 respecto a x = 0).

    Simple:   R_B = (ΣP·a + ΣW·c) / L ;  R_A = ΣP + ΣW - R_B
    Voladizo: R = ΣP + ΣW ;  M_empotramiento = -(ΣP·a + ΣW·c)  (momento negativo)
    donde W = w·(b - a) es la resultante y c = (a + b)/2 su posición.
    """
    a_p, P, a_d, b_d, w = _arreglos_cargas(d)
    W = w * (b_d - a_d)
    c = 0.5 * (a_d + b_d)
    carga_total = P.sum() + W.sum()
    momento_en_0 = (P * a_p).sum() + (W * c).sum()
    if d.apoyo == "simple":
        R_B = momento_en_0 / d.longitud_m
        return {"R_A_kN": float(carga_total - R_B), "R_B_kN": float(R_B)}
    return {"R_kN": float(carga_total), "M_empotramiento_kNm": float(-momento_en_0)}


def cortante_y_momento(d: DatosViga, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """V(x) y M(x) por el método de secciones, totalmente vectorizado.

    V(x) = R0 - ΣP·H(x-a) - Σ w·t
    M(x) = M0 + R0·x - ΣP·(x-a)₊ - Σ w·t·(x - a - t/2),  con t = clip(x-a, 0, b-a)
    (R0 y M0 son la reacción y el momento en x = 0; t es la longitud cargada
    a la izquierda de la sección.)
    """
    a_p, P, a_d, b_d, w = _arreglos_cargas(d)
    reac = reacciones(d)
    R0 = reac["R_A_kN"] if d.apoyo == "simple" else reac["R_kN"]
    M0 = 0.0 if d.apoyo == "simple" else reac["M_empotramiento_kNm"]

    xc = x[:, None]                                    # (n, 1): difunde contra las cargas
    V = R0 - ((xc >= a_p) * P).sum(axis=1)
    M = M0 + R0 * x - (np.clip(xc - a_p, 0.0, None) * P).sum(axis=1)
    t = np.clip(xc - a_d, 0.0, b_d - a_d)
    V = V - (w * t).sum(axis=1)
    M = M - (w * t * (xc - a_d - t / 2.0)).sum(axis=1)
    return V, M


def deflexion(x: np.ndarray, M: np.ndarray, EI: float, apoyo: str) -> tuple[np.ndarray, np.ndarray]:
    """Integra EI·y'' = M dos veces con SciPy (regla del trapecio acumulada).

    θ0 = ∫M/EI dx ,  y0 = ∫θ0 dx ;  luego se imponen las condiciones de borde:
      voladizo (empotrado en 0): θ(0)=0, y(0)=0  -> sin constantes adicionales
      simple: y(0)=0, y(L)=0 -> y = y0 + C1·x con C1 = -y0(L)/L
    Retorna (θ [rad], δ [m]) con δ = -y positivo hacia abajo.
    """
    theta0 = cumulative_trapezoid(M / EI, x, initial=0.0)
    y0 = cumulative_trapezoid(theta0, x, initial=0.0)
    if apoyo == "voladizo":
        return theta0, -y0
    C1 = -y0[-1] / x[-1]
    return theta0 + C1, -(y0 + C1 * x)


def analizar(d: DatosViga) -> Resultado:
    """Ejecuta el análisis completo: valida, calcula y chequea los criterios."""
    validar(d)
    x = np.linspace(0.0, d.longitud_m, d.n_puntos)
    I, S = propiedades_seccion(d.b_cm, d.h_cm)
    EI = d.E_GPa * GPA_A_KN_M2 * I
    V, M = cortante_y_momento(d, x)
    theta, delta_m = deflexion(x, M, EI, d.apoyo)
    delta_mm = delta_m * 1000.0

    i_M, i_d = int(np.argmax(np.abs(M))), int(np.argmax(np.abs(delta_mm)))
    M_max = float(np.abs(M[i_M]))
    sigma = M_max / S * KPA_A_MPA                      # σ = M/S [kN·m/m³ = kPa] -> MPa
    flecha_adm = d.longitud_m / d.limite_flecha * 1000.0
    delta_max = float(np.abs(delta_mm[i_d]))
    return Resultado(
        x=x, V=V, M=M, theta=theta, delta=delta_mm,
        reacciones=reacciones(d), I_m4=I, S_m3=S, EI_kNm2=EI,
        M_max_kNm=M_max, x_M_max_m=float(x[i_M]),
        V_max_kN=float(np.abs(V).max()),
        delta_max_mm=delta_max, x_delta_max_m=float(x[i_d]),
        sigma_max_MPa=float(sigma), flecha_adm_mm=float(flecha_adm),
        cumple_esfuerzo=bool(sigma <= d.sigma_adm_MPa),
        cumple_flecha=bool(delta_max <= flecha_adm),
        error_equilibrio_kNm=float(abs(M[-1])),         # en x = L el momento debe ser 0
    )


def tabla_estaciones(res: Resultado, n: int = 11) -> list[dict]:
    """Valores de x, V, M y δ en n estaciones equidistantes (para tablas del reporte)."""
    xs = np.linspace(res.x[0], res.x[-1], n)
    # np.round(...) + 0.0 evita mostrar «-0.000» (cero negativo) en la tabla
    V, M, dl = (np.round(np.interp(xs, res.x, arr), 3) + 0.0 for arr in (res.V, res.M, res.delta))
    return [{"x": f"{a:.3f}", "V": f"{b:.2f}", "M": f"{c:.2f}", "delta": f"{e:.3f}"}
            for a, b, c, e in zip(xs, V, M, dl)]


def verificar(d: DatosViga, res: Resultado) -> dict:
    """Chequeos numéricos independientes del resultado (se muestran en la memoria).

    1. Equilibrio vertical: ΣR debe igualar la carga total aplicada.
    2. Momento en x = L debe ser 0 (extremo apoyado o libre).
    3. Convergencia de malla: δmax con el doble de puntos no debe variar apreciablemente.
    """
    a_p, P, a_d, b_d, w = _arreglos_cargas(d)
    carga_total = float(P.sum() + (w * (b_d - a_d)).sum())
    suma_reacciones = res.reacciones.get("R_kN", None)
    if suma_reacciones is None:
        suma_reacciones = res.reacciones["R_A_kN"] + res.reacciones["R_B_kN"]
    n_fino = min(2 * d.n_puntos - 1, 20001)
    fino = analizar(DatosViga(**{**d.__dict__, "n_puntos": n_fino}))
    variacion = abs(fino.delta_max_mm - res.delta_max_mm) / max(fino.delta_max_mm, 1e-12)
    return {
        "carga_total_kN": carga_total, "suma_reacciones_kN": float(suma_reacciones),
        "error_fuerzas_kN": abs(carga_total - suma_reacciones),
        "momento_en_L_kNm": res.error_equilibrio_kNm,
        "delta_malla_fina_mm": fino.delta_max_mm, "variacion_malla": float(variacion),
        "ok": bool(abs(carga_total - suma_reacciones) < 1e-6 and res.error_equilibrio_kNm < 1e-6
                   and variacion < 1e-3),
    }
