"""Genera plantillas/memoria.docx (plantilla Jinja para docxtpl).

Se ejecuta una sola vez (o cuando se quiera cambiar el diseño):  python scripts/crear_plantilla.py
"""
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

AZUL = RGBColor(0x1F, 0x4E, 0x79)
DESTINO = Path(__file__).resolve().parent.parent / "plantillas" / "memoria.docx"


def sombrear(celda, color):
    pr = celda._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color)
    pr.append(sh)


def titulo(doc, texto, nivel=1):
    p = doc.add_heading(texto, level=nivel)
    for r in p.runs:
        r.font.color.rgb = AZUL; r.font.name = "Calibri"
    return p


def parrafo(doc, texto, negrita=False, centrado=False, size=10.5, mono=False):
    p = doc.add_paragraph()
    r = p.add_run(texto); r.bold = negrita; r.font.size = Pt(size)
    if mono:
        r.font.name = "Cambria Math"
    if centrado:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = negrita            # los subtítulos no quedan solos al final de página
    return p


def tabla(doc, encabezados, fila_jinja, anchos=None):
    """Tabla con fila de encabezado y una fila plantilla repetida con {%tr for %}."""
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in zip(t.rows[0].cells, encabezados):
        c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255); sombrear(c, "1F4E79")
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    inicio, *celdas, fin = fila_jinja
    filas = [t.add_row(), t.add_row(), t.add_row()]      # {%tr for %} / fila de datos / {%tr endfor %}
    filas[0].cells[0].text = inicio
    for c, txt in zip(filas[1].cells, celdas):
        c.text = txt; c.paragraphs[0].runs[0].font.size = Pt(9.5)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    filas[2].cells[0].text = fin
    if anchos:
        for fila in t.rows:
            for c, a in zip(fila.cells, anchos):
                c.width = Cm(a)
    doc.add_paragraph()
    return t


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
    sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)
    doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(10.5)

    # Encabezado y pie de página
    cab = sec.header.paragraphs[0]
    r = cab.add_run("Universidad Distrital Francisco José de Caldas · Ingeniería Civil · Programación II")
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x5F, 0x6B, 0x7A)
    pie = sec.footer.paragraphs[0]; pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pie.add_run("Memoria de cálculo generada automáticamente · {{ fecha }}"); r.font.size = Pt(8.5)

    # Portada / encabezado del proyecto
    p = parrafo(doc, "MEMORIA DE CÁLCULO", True, True, 22); p.runs[0].font.color.rgb = AZUL
    parrafo(doc, "Análisis de viga: cortante, momento flector y deflexión", False, True, 13)
    t = doc.add_table(rows=5, cols=2); t.style = "Table Grid"
    for fila, (k, v) in zip(t.rows, [("Proyecto", "{{ proyecto }}"), ("Cálculo", "{{ nombre_calculo }}"),
                                     ("Descripción", "{{ descripcion }}"), ("Autores", "{{ autores }}"),
                                     ("Fecha", "{{ fecha }}")]):
        fila.cells[0].text = k; fila.cells[1].text = v
        fila.cells[0].paragraphs[0].runs[0].bold = True; sombrear(fila.cells[0], "DCE6F1")
        fila.cells[0].width = Cm(4); fila.cells[1].width = Cm(13)

    titulo(doc, "1. Objetivo y descripción del problema")
    parrafo(doc, "Determinar las reacciones, los diagramas de fuerza cortante V(x) y momento flector M(x), y la "
                 "deflexión δ(x) de una viga prismática de sección rectangular con apoyo {{ apoyo_texto }}, "
                 "de luz L = {{ L }} m, sometida a las cargas indicadas. Se verifica el esfuerzo normal máximo "
                 "por flexión y la flecha máxima contra los valores admisibles.")

    titulo(doc, "2. Datos de entrada")
    tabla(doc, ["Parámetro", "Valor", "Unidad"],
          ["{%tr for f in datos_entrada %}", "{{ f.nombre }}", "{{ f.valor }}", "{{ f.unidad }}", "{%tr endfor %}"],
          [8, 4, 4])
    parrafo(doc, "Cargas puntuales (positivas hacia abajo)", True)
    tabla(doc, ["N.º", "Posición x [m]", "P [kN]"],
          ["{%tr for c in cargas_puntuales %}", "{{ c.n }}", "{{ c.x }}", "{{ c.P }}", "{%tr endfor %}"])
    parrafo(doc, "Cargas distribuidas uniformes", True)
    tabla(doc, ["N.º", "x inicial [m]", "x final [m]", "w [kN/m]"],
          ["{%tr for c in cargas_distribuidas %}", "{{ c.n }}", "{{ c.x_ini }}", "{{ c.x_fin }}", "{{ c.w }}",
           "{%tr endfor %}"])

    titulo(doc, "3. Fundamento teórico y ecuaciones")
    for txt in [
        "Propiedades de la sección rectangular:   I = b·h³ / 12      S = b·h² / 6",
        "Equilibrio estático:   ΣFy = 0 ;   ΣM = 0   →   reacciones R",
        "Cortante y momento (método de secciones):   V(x) = dM/dx ;   M(x) = M₀ + R₀·x − Σ P·(x − a)₊ − Σ w·t·(x − a − t/2)",
        "Elástica (Euler–Bernoulli):   E·I·d²y/dx² = M(x) ;   θ = ∫(M/EI)dx ;   y = ∫θ dx ;   δ = −y",
        "Esfuerzo por flexión:   σmax = |Mmax| / S",
        "Chequeos:   σmax ≤ σadm   y   δmax ≤ L / n"]:
        parrafo(doc, txt, mono=True, size=10)
    parrafo(doc, "Referencias: Hibbeler, R. C. Mecánica de materiales; Gere, J. & Goodno, B. Mechanics of Materials; "
                 "NSR-10, Título C (control de deflexiones).", size=9.5)

    titulo(doc, "4. Procedimiento de cálculo")
    for txt in [
        "1) Se calculan las propiedades de la sección: I = {{ I }} m⁴ ;  S = {{ S }} m³ ;  EI = E·I = {{ EI }} kN·m².",
        "2) Se obtienen las reacciones por equilibrio estático (ver tabla de reacciones).",
        "3) Se evalúan V(x) y M(x) con NumPy en {{ n_puntos }} puntos equidistantes (cálculo vectorizado).",
        "4) Se integra M/EI dos veces con scipy.integrate.cumulative_trapezoid y se imponen las condiciones de borde.",
        "5) Se determinan los valores máximos y se comparan con los admisibles."]:
        parrafo(doc, txt)

    titulo(doc, "5. Resultados")
    parrafo(doc, "Reacciones y resultados principales", True)
    tabla(doc, ["Magnitud", "Valor", "Unidad"],
          ["{%tr for f in resultados_principales %}", "{{ f.nombre }}", "{{ f.valor }}", "{{ f.unidad }}", "{%tr endfor %}"],
          [8, 4, 4])
    parrafo(doc, "Valores a lo largo de la viga", True)
    tabla(doc, ["x [m]", "V [kN]", "M [kN·m]", "δ [mm]"],
          ["{%tr for f in estaciones %}", "{{ f.x }}", "{{ f.V }}", "{{ f.M }}", "{{ f.delta }}", "{%tr endfor %}"])
    parrafo(doc, "Diagramas", True)
    imagen = doc.add_paragraph("{{ grafica }}")
    imagen.alignment = WD_ALIGN_PARAGRAPH.CENTER
    imagen.paragraph_format.keep_with_next = True
    parrafo(doc, "Figura 1. Esquema de cargas, diagrama de cortante, momento flector y deflexión.", False, True, 9)

    titulo(doc, "6. Verificación de resultados")
    tabla(doc, ["Verificación", "Resultado", "Estado"],
          ["{%tr for f in verificaciones %}", "{{ f.nombre }}", "{{ f.valor }}", "{{ f.estado }}", "{%tr endfor %}"],
          [8, 5, 3])

    titulo(doc, "7. Conclusiones")
    parrafo(doc, "{{ conclusion_esfuerzo }}")
    parrafo(doc, "{{ conclusion_flecha }}")
    p = parrafo(doc, "Dictamen global: {{ dictamen }}", True, size=12)
    p.runs[0].font.color.rgb = AZUL
    DESTINO.parent.mkdir(exist_ok=True)
    doc.save(DESTINO)
    print("Plantilla creada en", DESTINO)


if __name__ == "__main__":
    main()
