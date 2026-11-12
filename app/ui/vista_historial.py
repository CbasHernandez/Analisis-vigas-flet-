"""Vista «Historial»: listar, buscar/filtrar, reabrir, generar memoria y eliminar (con confirmación)."""
from __future__ import annotations

from typing import Callable

import flet as ft

from app.db import BaseDatos
from app.ui.tema import AZUL, AZUL_CLARO, GRIS, ROJO, VERDE, aviso
from app.ui.vista_calculo import generar_y_abrir_memoria

TODOS = "0"


class VistaHistorial:
    def __init__(self, page: ft.Page, bd: BaseDatos, al_abrir: Callable[[dict], None]):
        self.page, self.bd, self.al_abrir = page, bd, al_abrir
        self.buscador = ft.TextField(label="Buscar por proyecto o cálculo", prefix_icon=ft.Icons.SEARCH, dense=True,
                                     width=320, border_radius=6, on_change=self.refrescar)
        self.filtro = ft.Dropdown(label="Proyecto", value=TODOS, dense=True, width=260, border_radius=6,
                                  options=[ft.DropdownOption(key=TODOS, text="Todos")], on_select=self.refrescar)
        self.btn_borrar_proyecto = ft.OutlinedButton(content="Eliminar proyecto", icon=ft.Icons.DELETE_OUTLINE,
                                                     on_click=self.confirmar_eliminar_proyecto, disabled=True)
        self.contador = ft.Text("", color=GRIS)
        self.tabla = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.BOLD), numeric=n) for t, n in (
                ("ID", True), ("Proyecto", False), ("Cálculo", False), ("Fecha", False), ("M máx [kN·m]", True),
                ("δ máx [mm]", True), ("σ máx [MPa]", True), ("Estado", False), ("Acciones", False))],
            rows=[], heading_row_color=AZUL_CLARO, column_spacing=22, data_row_min_height=48)
        self.vacio = ft.Text("No hay cálculos guardados. Realice un cálculo y presione «Guardar».", color=GRIS)
        self.control = ft.Column([
            ft.Text("Historial de cálculos", size=20, weight=ft.FontWeight.BOLD, color=AZUL),
            ft.Row([self.buscador, self.filtro, self.btn_borrar_proyecto], spacing=12, wrap=True),
            self.contador,
            ft.Column([ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO), self.vacio],
                      scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=12, expand=True)

    def _proyecto_seleccionado(self) -> int | None:
        return None if self.filtro.value in (None, TODOS) else int(self.filtro.value)

    def refrescar(self, e=None) -> None:
        """Vuelve a consultar la base de datos con el texto y el proyecto elegidos."""
        try:
            proyectos = self.bd.listar_proyectos()
            seleccionado = self._proyecto_seleccionado()
            if seleccionado not in {p["id"] for p in proyectos}:
                self.filtro.value, seleccionado = TODOS, None
            self.filtro.options = [ft.DropdownOption(key=TODOS, text="Todos")] + [
                ft.DropdownOption(key=str(p["id"]), text=f"{p['nombre']} ({p['n_calculos']})") for p in proyectos]
            self.btn_borrar_proyecto.disabled = seleccionado is None
            filas = self.bd.listar_calculos(self.buscador.value or "", seleccionado)
            self.tabla.rows = [self._fila(f) for f in filas]
            self.vacio.visible = not filas
            self.contador.value = f"{len(filas)} cálculo(s)"
        except Exception as err:                        # noqa: BLE001
            aviso(self.page, f"No se pudo leer el historial: {err}", True)
        self.page.update()

    def _fila(self, f) -> ft.DataRow:
        cid = f["id"]
        estado = ft.Text("Cumple" if f["cumple"] else "No cumple", color=VERDE if f["cumple"] else ROJO,
                         weight=ft.FontWeight.W_600)
        acciones = ft.Row([
            ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Abrir en Cálculo", on_click=lambda e, i=cid: self.abrir(i)),
            ft.IconButton(ft.Icons.DESCRIPTION, tooltip="Generar memoria .docx",
                          on_click=lambda e, i=cid: generar_y_abrir_memoria(self.page, self.bd, i)),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ROJO,
                          on_click=lambda e, i=cid, n=f["nombre"]: self.confirmar_eliminar(i, n))], spacing=0)
        celdas = [str(cid), f["proyecto"], f["nombre"], f["creado"], f"{f['momento_max_kNm']:.2f}",
                  f"{f['flecha_max_mm']:.2f}", f"{f['esfuerzo_max_MPa']:.2f}"]
        return ft.DataRow(cells=[ft.DataCell(ft.Text(c)) for c in celdas] + [ft.DataCell(estado), ft.DataCell(acciones)])

    def abrir(self, calculo_id: int) -> None:
        calculo = self.bd.obtener_calculo(calculo_id)
        if calculo is None:
            aviso(self.page, "El cálculo ya no existe.", True)
            self.refrescar()
        else:
            self.al_abrir(calculo)

    # ---- eliminación con confirmación ----
    def _confirmar(self, titulo: str, mensaje: str, accion: Callable[[], None]) -> None:
        def aceptar(e):
            self.page.pop_dialog()
            try:
                accion()
                aviso(self.page, "Eliminado correctamente.")
            except Exception as err:                    # noqa: BLE001
                aviso(self.page, f"No se pudo eliminar: {err}", True)
            self.refrescar()

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text(titulo), content=ft.Text(mensaje),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton(content="Eliminar", bgcolor=ROJO, on_click=aceptar)]))

    def confirmar_eliminar(self, calculo_id: int, nombre: str) -> None:
        self._confirmar("Eliminar cálculo", f"¿Eliminar «{nombre}»? Esta acción no se puede deshacer.",
                        lambda: self.bd.eliminar_calculo(calculo_id))

    def confirmar_eliminar_proyecto(self, e) -> None:
        pid = self._proyecto_seleccionado()
        if pid is not None:
            self._confirmar("Eliminar proyecto", "Se eliminará el proyecto y TODOS sus cálculos. ¿Continuar?",
                            lambda: self.bd.eliminar_proyecto(pid))
