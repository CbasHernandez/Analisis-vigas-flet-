"""Colores y pequeños componentes reutilizables de la interfaz Flet."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import flet as ft

from app.modelo import ErrorDeEntrada

AZUL = "#1F4E79"
AZUL_CLARO = "#DCE6F1"
FONDO = "#F4F6F9"
GRIS = "#5F6B7A"
VERDE = "#2E7D32"
ROJO = "#B03A2E"


def campo(etiqueta: str, valor, unidad: str = "", ancho: int | None = None, **extra) -> ft.TextField:
    """Campo de texto numérico con la unidad visible a la derecha."""
    return ft.TextField(label=etiqueta, value=str(valor), suffix=unidad or None, dense=True, width=ancho,
                        border_radius=6, **extra)


def tarjeta(titulo: str, *contenido: ft.Control, ancho: int | None = None) -> ft.Container:
    """Panel blanco con borde suave y título."""
    return ft.Container(
        content=ft.Column([ft.Text(titulo, size=14, weight=ft.FontWeight.W_600, color=AZUL), *contenido],
                          spacing=10, tight=True),
        bgcolor="white", border_radius=10, padding=ft.Padding.all(16), width=ancho,
        border=ft.Border.all(1, "#D9DEE5"))


def metrica(titulo: str, valor: str, unidad: str, color: str = AZUL) -> ft.Container:
    """Tarjeta pequeña con un resultado destacado."""
    return ft.Container(
        content=ft.Column([ft.Text(titulo, size=11, color=GRIS),
                           ft.Row([ft.Text(valor, size=22, weight=ft.FontWeight.BOLD, color=color),
                                   ft.Text(unidad, size=12, color=GRIS)],
                                  spacing=4, vertical_alignment=ft.CrossAxisAlignment.END)],
                          spacing=2, tight=True),
        bgcolor="white", border_radius=10, padding=ft.Padding.symmetric(vertical=10, horizontal=14),
        border=ft.Border.all(1, "#D9DEE5"), width=190)


def aviso(page: ft.Page, mensaje: str, error: bool = False) -> None:
    """Muestra un SnackBar (verde = éxito, rojo = error)."""
    page.show_dialog(ft.SnackBar(content=ft.Text(mensaje, color="white"), bgcolor=ROJO if error else VERDE,
                                 duration=5000 if error else 3500))


def leer_numero(control: ft.TextField, nombre: str) -> float:
    """Convierte el texto de un campo en float; marca el campo y lanza ErrorDeEntrada si es inválido."""
    control.error = None
    texto = (control.value or "").strip().replace(",", ".")
    if not texto:
        control.error = "Obligatorio"
        raise ErrorDeEntrada(f"{nombre}: el campo está vacío.")
    try:
        return float(texto)
    except ValueError:
        control.error = "Número inválido"
        raise ErrorDeEntrada(f"{nombre}: «{control.value}» no es un número.") from None


def abrir_archivo(ruta: Path) -> None:
    """Abre un archivo con el programa predeterminado del sistema operativo."""
    if sys.platform.startswith("win"):
        os.startfile(ruta)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])
