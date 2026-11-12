"""La memoria Word debe contener los datos, la tabla (bucle for) y la gráfica."""
from docx import Document

from app.db import BaseDatos
from app.modelo import CargaDistribuida, CargaPuntual, DatosViga, analizar
from app.reporte import generar_memoria


def test_memoria_contiene_datos_tabla_y_grafica(tmp_path):
    datos = DatosViga(6, "simple", 21, 30, 50, 10, 360, [CargaPuntual(2, 20)], [CargaDistribuida(0, 6, 10)])
    r = analizar(datos)
    bd = BaseDatos(tmp_path / "t.db")
    cid = bd.guardar_calculo(bd.crear_proyecto("Proyecto X"), "Viga V-1", datos.a_dict(),
                             {"momento_max_kNm": r.M_max_kNm, "cortante_max_kN": r.V_max_kN,
                              "flecha_max_mm": r.delta_max_mm, "esfuerzo_max_MPa": r.sigma_max_MPa,
                              "cumple": r.cumple})
    ruta = generar_memoria(bd.obtener_calculo(cid), tmp_path)
    doc = Document(ruta)
    texto = "\n".join(p.text for p in doc.paragraphs) + "\n".join(
        c.text for t in doc.tables for f in t.rows for c in f.cells)
    assert ruta.exists() and "Proyecto X" in texto and "Viga V-1" in texto
    assert "{{" not in texto and "{%" not in texto                  # no quedaron etiquetas sin reemplazar
    assert len(doc.inline_shapes) == 1                              # la gráfica (InlineImage)
    tabla_est = [t for t in doc.tables if t.rows[0].cells[0].text == "x [m]"][0]
    assert len(tabla_est.rows) == 1 + 11                            # encabezado + 11 estaciones del for
    assert "LA VIGA CUMPLE" in texto
