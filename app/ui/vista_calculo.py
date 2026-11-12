"""Vista «Cálculo»: formulario de datos, ejecución, resultados, gráfica, guardado y memoria."""
from __future__ import annotations

import flet as ft

from app.db import BaseDatos
from app.graficas import figura_a_png, figura_diagramas
from app.modelo import (CargaDistribuida, CargaPuntual, DatosViga, ErrorDeEntrada, Resultado, analizar,
                        verificar)
from app.reporte import generar_memoria
from app.ui.tema import (AZUL, GRIS, ROJO, VERDE, abrir_archivo, aviso, campo, leer_numero, metrica,
                         tarjeta)


class VistaCalculo:
    """Controla el formulario y la zona de resultados. `self.control` es lo que se agrega a la página."""

    def __init__(self, page: ft.Page, bd: BaseDatos):
        self.page, self.bd = page, bd
        self.puntuales: list[CargaPuntual] = []
        self.distribuidas: list[CargaDistribuida] = []
        self.datos: DatosViga | None = None
        self.resultado: Resultado | None = None
        self.ultimo_id: int | None = None                 # id del último cálculo guardado/abierto

        # --- identificación ---
        self.f_proyecto = ft.TextField(label="Proyecto", value="Edificio de oficinas", dense=True, border_radius=6)
        self.f_nombre = ft.TextField(label="Nombre del cálculo", value="Viga V-1 entrepiso", dense=True, border_radius=6)
        # --- viga ---
        self.f_apoyo = ft.Dropdown(label="Tipo de apoyo", value="simple", dense=True, border_radius=6,
                                   options=[ft.DropdownOption(key="simple", text="Simplemente apoyada"),
                                            ft.DropdownOption(key="voladizo", text="Voladizo (empotrada-libre)")])
        self.f_L = campo("Longitud L", 6, "m", 150)
        self.f_E = campo("Módulo E", 21, "GPa", 150)
        self.f_b = campo("Base b", 30, "cm", 150)
        self.f_h = campo("Altura h", 50, "cm", 150)
        self.f_sigma = campo("σ admisible", 10, "MPa", 150)
        self.f_limite = campo("n en δadm = L/n", 360, "", 150)
        # --- cargas ---
        self.p_x, self.p_P = campo("x", 2, "m", 100), campo("P", 20, "kN", 100)
        self.d_x1, self.d_x2, self.d_w = campo("x ini", 0, "m", 90), campo("x fin", 6, "m", 90), campo("w", 10, "kN/m", 100)
        self.lista_p, self.lista_d = ft.Column(spacing=0, tight=True), ft.Column(spacing=0, tight=True)
        self.distribuidas.append(CargaDistribuida(0.0, 6.0, 10.0))     # ejemplo inicial = caso resuelto a mano
        self._pintar_cargas()

        # --- resultados ---
        self.panel_metricas = ft.Row(wrap=True, spacing=12, run_spacing=12)
        self.banner = ft.Container(visible=False)
        self.imagen = ft.Image(src=b"", width=720, height=630, fit=ft.BoxFit.CONTAIN, visible=False)
        self.texto_vacio = ft.Container(
            content=ft.Text("Ingrese los datos y presione «Calcular» para ver resultados y diagramas.", color=GRIS),
            padding=ft.Padding.all(30))
        self.texto_verif = ft.Text("", size=12, color=GRIS)
        self.btn_guardar = ft.Button(content="Guardar", icon=ft.Icons.SAVE, on_click=self.guardar, disabled=True)
        self.btn_memoria = ft.Button(content="Generar memoria .docx", icon=ft.Icons.DESCRIPTION,
                                     on_click=self.memoria, disabled=True)

        formulario = ft.Column([
            ft.Row([ft.FilledButton(content="Calcular", icon=ft.Icons.PLAY_ARROW, on_click=self.calcular),
                    self.btn_guardar, self.btn_memoria], spacing=8, wrap=True),
            tarjeta("Identificación", self.f_proyecto, self.f_nombre),
            tarjeta("Viga y material", self.f_apoyo,
                    ft.Row([self.f_L, self.f_E], spacing=10), ft.Row([self.f_b, self.f_h], spacing=10),
                    ft.Row([self.f_sigma, self.f_limite], spacing=10)),
            tarjeta("Cargas puntuales (↓ positiva)",
                    ft.Row([self.p_x, self.p_P, ft.IconButton(ft.Icons.ADD, tooltip="Agregar carga puntual",
                                                              on_click=self.agregar_puntual)], spacing=8),
                    self.lista_p),
            tarjeta("Cargas distribuidas uniformes",
                    ft.Row([self.d_x1, self.d_x2, self.d_w,
                            ft.IconButton(ft.Icons.ADD, tooltip="Agregar carga distribuida",
                                          on_click=self.agregar_distribuida)], spacing=6),
                    self.lista_d),
        ], spacing=12, scroll=ft.ScrollMode.AUTO, width=440)

        resultados = ft.Column([
            ft.Text("Resultados", size=20, weight=ft.FontWeight.BOLD, color=AZUL),
            self.texto_vacio, self.banner, self.panel_metricas, self.texto_verif, self.imagen,
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

        self.control = ft.Row([formulario, ft.VerticalDivider(width=1), resultados], expand=True,
                              vertical_alignment=ft.CrossAxisAlignment.START, spacing=16)

    # ------------------------------------------------------------------ cargas
    def _pintar_cargas(self) -> None:
        self.lista_p.controls = [self._fila_carga(f"P{i}: x = {c.posicion_m:g} m,  P = {c.P_kN:g} kN",
                                                  lambda e, k=i - 1: self._quitar(self.puntuales, k))
                                 for i, c in enumerate(self.puntuales, 1)]
        self.lista_d.controls = [self._fila_carga(f"w{i}: de {c.x_ini_m:g} a {c.x_fin_m:g} m,  w = {c.w_kN_m:g} kN/m",
                                                  lambda e, k=i - 1: self._quitar(self.distribuidas, k))
                                 for i, c in enumerate(self.distribuidas, 1)]

    def _fila_carga(self, texto: str, al_quitar) -> ft.Row:
        return ft.Row([ft.Text(texto, size=12, expand=True),
                       ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, tooltip="Quitar", on_click=al_quitar)],
                      spacing=0)

    def _quitar(self, lista: list, indice: int) -> None:
        del lista[indice]
        self._pintar_cargas()
        self.page.update()

    def agregar_puntual(self, e) -> None:
        try:
            self.puntuales.append(CargaPuntual(leer_numero(self.p_x, "Posición x"), leer_numero(self.p_P, "P")))
            self._pintar_cargas()
        except ErrorDeEntrada as err:
            aviso(self.page, str(err), True)
        self.page.update()

    def agregar_distribuida(self, e) -> None:
        try:
            self.distribuidas.append(CargaDistribuida(leer_numero(self.d_x1, "x inicial"),
                                                      leer_numero(self.d_x2, "x final"), leer_numero(self.d_w, "w")))
            self._pintar_cargas()
        except ErrorDeEntrada as err:
            aviso(self.page, str(err), True)
        self.page.update()

    # ------------------------------------------------------------------ cálculo
    def _leer_datos(self) -> DatosViga:
        return DatosViga(
            longitud_m=leer_numero(self.f_L, "Longitud L"), apoyo=self.f_apoyo.value or "simple",
            E_GPa=leer_numero(self.f_E, "Módulo E"), b_cm=leer_numero(self.f_b, "Base b"),
            h_cm=leer_numero(self.f_h, "Altura h"), sigma_adm_MPa=leer_numero(self.f_sigma, "σ admisible"),
            limite_flecha=leer_numero(self.f_limite, "Límite de flecha n"),
            puntuales=list(self.puntuales), distribuidas=list(self.distribuidas))

    def _ejecutar(self) -> bool:
        """Lee, valida y calcula. Devuelve True si hubo resultado; si no, muestra el error sin cerrar la app."""
        try:
            datos = self._leer_datos()
            resultado = analizar(datos)
        except ErrorDeEntrada as err:
            aviso(self.page, str(err), True)
            self.page.update()
            return False
        except Exception as err:                       # noqa: BLE001  (última red de seguridad de la interfaz)
            aviso(self.page, f"Error inesperado al calcular: {err}", True)
            self.page.update()
            return False
        self.datos, self.resultado = datos, resultado
        self._mostrar(datos, resultado)
        return True

    def calcular(self, e) -> None:
        if self._ejecutar():
            self.ultimo_id = None                      # el resultado aún no está guardado
            self.btn_memoria.disabled = True
            aviso(self.page, "Cálculo realizado correctamente.")
            self.page.update()

    def _mostrar(self, d: DatosViga, r: Resultado) -> None:
        """Actualiza métricas, banner de cumplimiento y gráfica con el nuevo resultado."""
        ok = lambda b: VERDE if b else ROJO                                   # noqa: E731
        reac = ([("Reacción R", r.reacciones["R_kN"], "kN"), ("Momento empotr. M₀", r.reacciones["M_empotramiento_kNm"], "kN·m")]
                if "R_kN" in r.reacciones else
                [("Reacción R_A", r.reacciones["R_A_kN"], "kN"), ("Reacción R_B", r.reacciones["R_B_kN"], "kN")])
        self.panel_metricas.controls = (
            [metrica(n, f"{v:.2f}", u) for n, v, u in reac] + [
                metrica("|V| máximo", f"{r.V_max_kN:.2f}", "kN"),
                metrica(f"|M| máx (x = {r.x_M_max_m:.2f} m)", f"{r.M_max_kNm:.2f}", "kN·m"),
                metrica("σ máximo", f"{r.sigma_max_MPa:.2f}", f"MPa (adm {d.sigma_adm_MPa:g})", ok(r.cumple_esfuerzo)),
                metrica(f"δ máx (x = {r.x_delta_max_m:.2f} m)", f"{r.delta_max_mm:.2f}",
                        f"mm (adm {r.flecha_adm_mm:.2f})", ok(r.cumple_flecha))])
        self.banner.content = ft.Row([
            ft.Icon(ft.Icons.CHECK_CIRCLE if r.cumple else ft.Icons.CANCEL, color="white"),
            ft.Text("LA VIGA CUMPLE esfuerzo y flecha" if r.cumple else
                    "LA VIGA NO CUMPLE: " + ("esfuerzo " if not r.cumple_esfuerzo else "") +
                    ("flecha" if not r.cumple_flecha else ""), color="white", weight=ft.FontWeight.W_600)])
        self.banner.bgcolor, self.banner.border_radius = ok(r.cumple), 8
        self.banner.padding, self.banner.visible = ft.Padding.symmetric(vertical=10, horizontal=14), True
        ver = verificar(d, r)
        self.texto_verif.value = (f"Verificación numérica: error de equilibrio {ver['error_fuerzas_kN']:.1e} kN, "
                                  f"M(L) = {ver['momento_en_L_kNm']:.1e} kN·m, variación de malla "
                                  f"{ver['variacion_malla'] * 100:.4f} % → {'OK' if ver['ok'] else 'REVISAR'}")
        self.imagen.src = figura_a_png(figura_diagramas(d, r, compacta=True), dpi=100)
        self.imagen.visible, self.texto_vacio.visible = True, False
        self.btn_guardar.disabled = False

    # ------------------------------------------------------------------ guardar / memoria
    def guardar(self, e) -> None:
        try:
            if not self._ejecutar():
                return
            proyecto, nombre = (self.f_proyecto.value or "").strip(), (self.f_nombre.value or "").strip()
            self.f_proyecto.error = None if proyecto else "Obligatorio"
            self.f_nombre.error = None if nombre else "Obligatorio"
            if not proyecto or not nombre:
                aviso(self.page, "Escriba el nombre del proyecto y del cálculo para guardar.", True)
                self.page.update()
                return
            r = self.resultado
            self.ultimo_id = self.bd.guardar_calculo(
                self.bd.obtener_o_crear_proyecto(proyecto), nombre, self.datos.a_dict(),
                {"momento_max_kNm": r.M_max_kNm, "cortante_max_kN": r.V_max_kN, "flecha_max_mm": r.delta_max_mm,
                 "esfuerzo_max_MPa": r.sigma_max_MPa, "cumple": r.cumple})
            self.btn_memoria.disabled = False
            aviso(self.page, f"Cálculo guardado en «{proyecto}» (ID {self.ultimo_id}).")
        except Exception as err:                       # noqa: BLE001
            aviso(self.page, f"No se pudo guardar: {err}", True)
        self.page.update()

    def memoria(self, e) -> None:
        if self.ultimo_id is None:
            aviso(self.page, "Primero guarde el cálculo para generar su memoria.", True)
            self.page.update()
            return
        generar_y_abrir_memoria(self.page, self.bd, self.ultimo_id)

    # ------------------------------------------------------------------ reabrir desde historial
    def cargar(self, calculo: dict) -> None:
        """Rellena el formulario con un cálculo guardado y lo recalcula."""
        d = DatosViga.desde_dict(calculo["datos"])
        self.f_proyecto.value, self.f_nombre.value = calculo["proyecto"], calculo["nombre"]
        self.f_apoyo.value = d.apoyo
        for control, valor in ((self.f_L, d.longitud_m), (self.f_E, d.E_GPa), (self.f_b, d.b_cm), (self.f_h, d.h_cm),
                               (self.f_sigma, d.sigma_adm_MPa), (self.f_limite, d.limite_flecha)):
            control.value, control.error = f"{valor:g}", None
        self.puntuales, self.distribuidas = list(d.puntuales), list(d.distribuidas)
        self._pintar_cargas()
        if self._ejecutar():
            self.ultimo_id = calculo["id"]
            self.btn_memoria.disabled = False
        self.page.update()


def generar_y_abrir_memoria(page: ft.Page, bd: BaseDatos, calculo_id: int) -> None:
    """Genera la memoria .docx de un cálculo guardado y la abre. Compartido por Cálculo e Historial."""
    try:
        calculo = bd.obtener_calculo(calculo_id)
        if calculo is None:
            aviso(page, "El cálculo ya no existe en la base de datos.", True)
        else:
            ruta = generar_memoria(calculo)
            aviso(page, f"Memoria generada: salidas/{ruta.name}")
            try:
                abrir_archivo(ruta)
            except Exception:                           # noqa: BLE001  (p. ej. sin programa asociado)
                pass
    except Exception as err:                            # noqa: BLE001
        aviso(page, f"No se pudo generar la memoria: {err}", True)
    page.update()
