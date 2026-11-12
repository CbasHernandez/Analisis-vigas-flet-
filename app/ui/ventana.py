"""Ventana principal: panel de navegación lateral y cambio entre vistas."""
from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from app.db import RUTA_BD_DEFECTO, BaseDatos
from app.ui.tema import AZUL, FONDO, GRIS
from app.ui.vista_calculo import VistaCalculo
from app.ui.vista_historial import VistaHistorial


def main(page: ft.Page, ruta_bd=RUTA_BD_DEFECTO) -> None:
    """Construye la ventana. `ruta_bd` permite usar otra base (p. ej. para generar capturas)."""
    page.title = "Análisis de Vigas — Ingeniería Civil"
    page.theme = ft.Theme(color_scheme_seed=AZUL)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.width, page.window.height = 1360, 880
    page.window.min_width, page.window.min_height = 1000, 650

    bd = BaseDatos(ruta_bd)                                 # crea la base y las tablas si no existen
    zona = ft.Container(expand=True, padding=ft.Padding.all(20), bgcolor=FONDO)

    def abrir_en_calculo(calculo: dict) -> None:
        vista_calculo.cargar(calculo)
        riel.selected_index = 0
        zona.content = vista_calculo.control
        page.update()

    vista_calculo = VistaCalculo(page, bd)
    vista_historial = VistaHistorial(page, bd, abrir_en_calculo)

    def cambiar_vista(e) -> None:
        if riel.selected_index == 1:
            vista_historial.refrescar()
        zona.content = vista_historial.control if riel.selected_index == 1 else vista_calculo.control
        page.update()

    riel = ft.NavigationRail(
        selected_index=0, label_type=ft.NavigationRailLabelType.ALL, min_width=96, bgcolor="white",
        leading=ft.Container(ft.Column([ft.Icon(ft.Icons.ENGINEERING, color=AZUL, size=34),
                                        ft.Text("Vigas", weight=ft.FontWeight.BOLD, color=AZUL),
                                        ft.Text("v1.0", size=10, color=GRIS)],
                                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                             padding=ft.Padding.symmetric(vertical=16)),
        destinations=[ft.NavigationRailDestination(icon=ft.Icons.CALCULATE_OUTLINED, selected_icon=ft.Icons.CALCULATE,
                                                   label="Cálculo"),
                      ft.NavigationRailDestination(icon=ft.Icons.HISTORY_OUTLINED, selected_icon=ft.Icons.HISTORY,
                                                   label="Historial")],
        on_change=cambiar_vista)

    zona.content = vista_calculo.control
    page.data = SimpleNamespace(calculo=vista_calculo, historial=vista_historial, riel=riel, cambiar=cambiar_vista, bd=bd)
    page.add(ft.Row([riel, ft.VerticalDivider(width=1), zona], expand=True, spacing=0))
