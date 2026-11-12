"""Genera las capturas del README y ejemplos/memoria_ejemplo.docx usando la interfaz REAL.

Llama a los mismos manejadores que los botones y toma pantallazos de la ventana de Flet.
Requiere un display (en Linux sin pantalla:  xvfb-run -a -s "-screen 0 1500x950x24" python scripts/generar_capturas.py)
y la herramienta `import` de ImageMagick para los pantallazos. Usa una base de datos temporal.
"""
import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import flet as ft

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.reporte import generar_memoria  # noqa: E402
from app.ui.ventana import main  # noqa: E402

CAPTURAS = RAIZ / "ejemplos" / "capturas"
BD_TEMPORAL = Path(tempfile.mkdtemp()) / "capturas.db"


def foto(nombre: str) -> None:
    destino = str(CAPTURAS / nombre)
    subprocess.run(["import", "-window", "root", destino], check=True)
    subprocess.run(["convert", destino, "-fuzz", "1%", "-trim", "+repage", destino], check=True)  # quita el fondo negro de Xvfb
    print("captura:", nombre)


async def demo(page: ft.Page) -> None:
    main(page, BD_TEMPORAL)
    page.window.width, page.window.height = 1260, 700      # cabe en el display virtual
    page.update()
    app = page.data
    await asyncio.sleep(4)
    foto("01_calculo_formulario.png")

    # Se agrega una carga puntual con el mismo manejador del botón «+» y se calcula
    app.calculo.p_x.value, app.calculo.p_P.value = "2", "20"
    app.calculo.agregar_puntual(None)
    app.calculo.calcular(None)
    await asyncio.sleep(3)
    foto("02_resultados_y_graficas.png")

    # Entrada inválida: campo vacío -> mensaje de error, sin cerrar la aplicación
    app.calculo.f_L.value = ""
    app.calculo.calcular(None)
    await asyncio.sleep(1.5)
    foto("03_validacion_de_entradas.png")
    app.calculo.f_L.value, app.calculo.f_L.error = "6", None

    # Guardar y generar la memoria de ejemplo desde un cálculo guardado
    app.calculo.guardar(None)
    calculo = app.bd.obtener_calculo(app.calculo.ultimo_id)
    ruta = generar_memoria(calculo, Path(tempfile.mkdtemp()))
    shutil.copy(ruta, RAIZ / "ejemplos" / "memoria_ejemplo.docx")
    print("memoria de ejemplo:", RAIZ / "ejemplos" / "memoria_ejemplo.docx")

    # Voladizo guardado para que el historial muestre más de un registro
    app.calculo.f_apoyo.value, app.calculo.f_nombre.value = "voladizo", "Voladizo balcón"
    app.calculo.f_L.value, app.calculo.f_limite.value = "2.5", "180"
    app.calculo.puntuales.clear(); app.calculo.distribuidas.clear()
    app.calculo.d_x1.value, app.calculo.d_x2.value, app.calculo.d_w.value = "0", "2.5", "8"
    app.calculo.agregar_distribuida(None)
    app.calculo.guardar(None)

    app.riel.selected_index = 1
    app.cambiar(None)
    await asyncio.sleep(2)
    foto("04_historial.png")
    await page.window.destroy()


if __name__ == "__main__":
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    ft.run(demo)
