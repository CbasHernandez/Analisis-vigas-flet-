"""Gráficas técnicas con Matplotlib. Devuelven figuras; no abren ventanas.

Se usa matplotlib.figure.Figure (sin pyplot) para que sea seguro dentro de Flet
y se pueda reutilizar la misma imagen en la interfaz y en la memoria de cálculo.
"""
from __future__ import annotations

import io

import numpy as np
from matplotlib.figure import Figure

from app.modelo import DatosViga, Resultado

AZUL, ROJO, VERDE, GRIS = "#1F4E79", "#B03A2E", "#2E7D32", "#5F6B7A"


def _esquema_cargas(ax, d: DatosViga) -> None:
    """Dibuja la viga, los apoyos y las cargas (solo dibujo, no cálculo)."""
    L = d.longitud_m
    ax.plot([0, L], [0, 0], color="black", lw=5, solid_capstyle="butt", label="Viga")
    if d.apoyo == "simple":
        ax.plot([0], [-0.12], marker="^", ms=13, color=GRIS)
        ax.plot([L], [-0.12], marker="o", ms=11, color=GRIS)
    else:
        ax.plot([0, 0], [-0.4, 0.4], color=GRIS, lw=7)
    escala = max([abs(c.P_kN) for c in d.puntuales] + [abs(c.w_kN_m) * 2 for c in d.distribuidas] + [1.0])
    for c in d.distribuidas:
        h = 0.5 + 0.5 * abs(c.w_kN_m) / escala
        ax.fill_between([c.x_ini_m, c.x_fin_m], 0.05, h, color=AZUL, alpha=0.25)
        ax.text((c.x_ini_m + c.x_fin_m) / 2, h + 0.08, f"w = {c.w_kN_m:g} kN/m", ha="center", fontsize=8, color=AZUL)
    for c in d.puntuales:
        h = 0.5 + 0.5 * abs(c.P_kN) / escala
        sentido = 1 if c.P_kN > 0 else -1
        ax.annotate("", xy=(c.posicion_m, 0.05 if sentido > 0 else h), xytext=(c.posicion_m, h if sentido > 0 else 0.05),
                    arrowprops=dict(arrowstyle="-|>", color=ROJO, lw=2))
        ax.text(c.posicion_m, h + 0.08, f"P = {c.P_kN:g} kN", ha="center", fontsize=8, color=ROJO)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlim(-0.05 * L, 1.05 * L)
    ax.set_yticks([])
    ax.set_title("Esquema de la viga y cargas (kN, kN/m)", fontsize=10, loc="left")
    ax.set_xlabel("Posición x [m]", fontsize=9)


def _curva(ax, x, y, color, etiqueta, ylabel, titulo, marcar_max=True, relleno=True) -> None:
    ax.plot(x, y, color=color, lw=1.8, label=etiqueta)
    if relleno:
        ax.fill_between(x, y, 0, color=color, alpha=0.15)
    ax.axhline(0, color="black", lw=0.8)
    if marcar_max:
        i = int(np.argmax(np.abs(y)))
        ax.plot(x[i], y[i], "o", color=color)
        ax.annotate(f"{y[i]:.2f}", (x[i], y[i]), textcoords="offset points", xytext=(6, 6), fontsize=8)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(titulo, fontsize=10, loc="left")
    ax.grid(alpha=0.3)
    ax.margins(y=0.2)
    ax.legend(loc="upper right", fontsize=8)


def figura_diagramas(d: DatosViga, r: Resultado, compacta: bool = False) -> Figure:
    """Esquema + diagramas de cortante, momento y deflexión (δ positiva hacia abajo)."""
    fig = Figure(figsize=(8, 8.2 if not compacta else 7), dpi=110, layout="constrained")
    ax0, ax1, ax2, ax3 = fig.subplots(4, 1, height_ratios=[0.9, 1, 1, 1])
    _esquema_cargas(ax0, d)
    _curva(ax1, r.x, r.V, AZUL, "V(x)", "V [kN]", "Diagrama de fuerza cortante")
    _curva(ax2, r.x, r.M, ROJO, "M(x)", "M [kN·m]", "Diagrama de momento flector (M > 0: tracción en la fibra inferior)")
    _curva(ax3, r.x, r.delta, VERDE, "δ(x)", "δ [mm]", "Deflexión (positiva hacia abajo)")
    ax3.axhline(r.flecha_adm_mm, color="black", ls="--", lw=1.2,
                label=f"δ adm = L/{d.limite_flecha:g} = {r.flecha_adm_mm:.2f} mm")
    ax3.invert_yaxis()
    ax3.legend(loc="lower right", fontsize=8)
    ax3.set_xlabel("Posición x [m]", fontsize=9)
    for ax in (ax1, ax2):
        ax.set_xlim(0, d.longitud_m)
    ax3.set_xlim(0, d.longitud_m)
    return fig


def figura_a_png(fig: Figure, dpi: int = 130) -> bytes:
    """Convierte la figura en bytes PNG (para Flet y para InlineImage de docxtpl)."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    return buffer.getvalue()
