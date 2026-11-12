"""Pruebas del modelo contra soluciones cerradas y un caso resuelto a mano."""
import numpy as np
import pytest

from app.modelo import (CargaDistribuida, CargaPuntual, DatosViga, ErrorDeEntrada,
                        analizar, propiedades_seccion, tabla_estaciones, validar)


def viga(apoyo="simple", L=6.0, puntuales=(), distribuidas=(), b=30.0, h=50.0, E=21.0, n=2001):
    return DatosViga(L, apoyo, E, b, h, sigma_adm_MPa=10.0, limite_flecha=360,
                     puntuales=list(puntuales), distribuidas=list(distribuidas), n_puntos=n)


# ---- Caso 1 (RESUELTO A MANO, validación de C1) -----------------------------------------
# Viga simple L = 6 m, w = 10 kN/m en toda la luz, sección 30x50 cm, E = 21 GPa.
#   I  = 0.30·0.50³/12 = 3.125e-3 m⁴      EI = 21e6·3.125e-3 = 65 625 kN·m²
#   S  = 0.30·0.50²/6  = 0.0125 m³
#   R  = wL/2 = 30 kN        Mmax = wL²/8 = 45 kN·m (en x = 3 m)
#   σ  = 45/0.0125 = 3 600 kPa = 3.6 MPa
#   δ  = 5wL⁴/(384EI) = 5·10·1296/(384·65625) = 2.5714e-3 m = 2.571 mm
def test_caso_manual_viga_simple_carga_uniforme():
    r = analizar(viga(distribuidas=[CargaDistribuida(0, 6, 10)]))
    assert r.I_m4 == pytest.approx(3.125e-3)
    assert r.EI_kNm2 == pytest.approx(65625.0)
    assert r.reacciones["R_A_kN"] == pytest.approx(30.0)
    assert r.reacciones["R_B_kN"] == pytest.approx(30.0)
    assert r.M_max_kNm == pytest.approx(45.0, rel=1e-6)
    assert r.x_M_max_m == pytest.approx(3.0, abs=1e-6)
    assert r.sigma_max_MPa == pytest.approx(3.6, rel=1e-6)
    assert r.delta_max_mm == pytest.approx(2.5714, rel=1e-3)
    assert r.cumple


# ---- Caso 2: viga simple con carga puntual al centro ------------------------------------
def test_viga_simple_carga_puntual_central():
    P, L = 20.0, 4.0
    r = analizar(viga(L=L, puntuales=[CargaPuntual(2.0, P)]))
    assert r.reacciones["R_A_kN"] == pytest.approx(P / 2)
    assert r.M_max_kNm == pytest.approx(P * L / 4, rel=1e-6)
    assert r.delta_max_mm == pytest.approx(P * L**3 / (48 * r.EI_kNm2) * 1000, rel=1e-3)


# ---- Caso 3: voladizo con carga puntual en el extremo libre -----------------------------
def test_voladizo_carga_puntual_en_el_extremo():
    P, L = 10.0, 3.0
    r = analizar(viga("voladizo", L=L, puntuales=[CargaPuntual(L, P)]))
    assert r.reacciones["R_kN"] == pytest.approx(P)
    assert r.reacciones["M_empotramiento_kNm"] == pytest.approx(-P * L)
    assert r.M[0] == pytest.approx(-P * L, rel=1e-9)
    assert r.delta_max_mm == pytest.approx(P * L**3 / (3 * r.EI_kNm2) * 1000, rel=1e-3)
    assert r.x_delta_max_m == pytest.approx(L)


# ---- Caso 4: voladizo con carga uniforme -------------------------------------------------
def test_voladizo_carga_uniforme():
    w, L = 8.0, 2.5
    r = analizar(viga("voladizo", L=L, distribuidas=[CargaDistribuida(0, L, w)]))
    assert r.M_max_kNm == pytest.approx(w * L**2 / 2, rel=1e-6)
    assert r.delta_max_mm == pytest.approx(w * L**4 / (8 * r.EI_kNm2) * 1000, rel=1e-3)


# ---- Caso 5: superposición y equilibrio con cargas mixtas y parciales --------------------
def test_superposicion_y_equilibrio():
    c1, c2 = CargaPuntual(1.5, 12.0), CargaDistribuida(2.0, 5.0, 6.0)
    mixta = analizar(viga(puntuales=[c1], distribuidas=[c2]))
    sola_p = analizar(viga(puntuales=[c1]))
    sola_d = analizar(viga(distribuidas=[c2]))
    assert np.allclose(mixta.M, sola_p.M + sola_d.M)
    assert np.allclose(mixta.delta, sola_p.delta + sola_d.delta)
    assert mixta.reacciones["R_A_kN"] + mixta.reacciones["R_B_kN"] == pytest.approx(12 + 6 * 3)
    assert mixta.error_equilibrio_kNm < 1e-9
    assert abs(mixta.delta[0]) < 1e-12 and abs(mixta.delta[-1]) < 1e-9   # condiciones de borde


def test_dimensiones_de_la_seccion():
    I, S = propiedades_seccion(30, 50)
    assert (I, S) == (pytest.approx(3.125e-3), pytest.approx(0.0125))


def test_criterio_no_cumple_con_seccion_pequena():
    r = analizar(viga(h=20.0, b=15.0, distribuidas=[CargaDistribuida(0, 6, 10)]))
    assert not r.cumple_esfuerzo and not r.cumple_flecha and not r.cumple


def test_tabla_estaciones():
    r = analizar(viga(distribuidas=[CargaDistribuida(0, 6, 10)]))
    filas = tabla_estaciones(r, 7)
    assert len(filas) == 7 and filas[0]["x"] == "0.000" and filas[3]["M"] == "45.00"


@pytest.mark.parametrize("cambio", [
    {"longitud_m": 0}, {"longitud_m": float("nan")}, {"E_GPa": -1}, {"b_cm": 0},
    {"apoyo": "empotrada"}, {"puntuales": []},
])
def test_validacion_rechaza_datos_invalidos(cambio):
    datos = viga(puntuales=[CargaPuntual(1, 5)])
    for k, v in cambio.items():
        setattr(datos, k, v)
    with pytest.raises(ErrorDeEntrada):
        validar(datos)


def test_validacion_de_cargas_fuera_de_la_viga():
    with pytest.raises(ErrorDeEntrada):
        validar(viga(puntuales=[CargaPuntual(7, 5)]))
    with pytest.raises(ErrorDeEntrada):
        validar(viga(distribuidas=[CargaDistribuida(4, 2, 5)]))


def test_serializacion_ida_y_vuelta():
    d = viga(puntuales=[CargaPuntual(1, 5)], distribuidas=[CargaDistribuida(0, 3, 2)])
    assert DatosViga.desde_dict(d.a_dict()).a_dict() == d.a_dict()


def test_verificacion_numerica_pasa_en_caso_manual():
    from app.modelo import verificar
    d = viga(distribuidas=[CargaDistribuida(0, 6, 10)], n=1001)
    v = verificar(d, analizar(d))
    assert v["carga_total_kN"] == pytest.approx(60.0) and v["suma_reacciones_kN"] == pytest.approx(60.0)
    assert v["ok"] and v["variacion_malla"] < 1e-3
