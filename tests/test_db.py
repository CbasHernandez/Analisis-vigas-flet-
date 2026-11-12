"""Pruebas de la capa SQLite usando una base temporal."""
import sqlite3

import pytest

from app.db import BaseDatos

RESUMEN = {"momento_max_kNm": 45.0, "cortante_max_kN": 30.0, "flecha_max_mm": 2.57,
           "esfuerzo_max_MPa": 3.6, "cumple": True}


@pytest.fixture
def bd(tmp_path):
    return BaseDatos(tmp_path / "prueba.db")


def test_crea_las_tablas_automaticamente(bd):
    con = sqlite3.connect(bd.ruta)
    tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert {"proyectos", "calculos"} <= tablas


def test_guardar_listar_buscar_reabrir_y_eliminar(bd):
    pid = bd.crear_proyecto("Edificio A", "Vigas de entrepiso")
    cid = bd.guardar_calculo(pid, "Viga V-1", {"longitud_m": 6.0}, RESUMEN)
    assert [f["nombre"] for f in bd.listar_calculos()] == ["Viga V-1"]
    assert bd.listar_calculos(texto="edificio")[0]["id"] == cid       # busca por nombre del proyecto
    assert bd.listar_calculos(texto="no existe") == []
    reabierto = bd.obtener_calculo(cid)
    assert reabierto["datos"] == {"longitud_m": 6.0} and reabierto["proyecto"] == "Edificio A"
    bd.renombrar_calculo(cid, "V-1 final")
    assert bd.obtener_calculo(cid)["nombre"] == "V-1 final"
    bd.eliminar_calculo(cid)
    assert bd.obtener_calculo(cid) is None


def test_eliminar_proyecto_borra_sus_calculos_por_cascada(bd):
    pid = bd.crear_proyecto("P")
    bd.guardar_calculo(pid, "c1", {}, RESUMEN)
    bd.eliminar_proyecto(pid)
    assert bd.listar_calculos() == []


def test_llave_foranea_rechaza_proyecto_inexistente(bd):
    with pytest.raises(sqlite3.IntegrityError):
        bd.guardar_calculo(999, "huérfano", {}, RESUMEN)


def test_consultas_parametrizadas_resisten_inyeccion(bd):
    pid = bd.crear_proyecto("Seguro")
    bd.guardar_calculo(pid, "c1", {}, RESUMEN)
    assert bd.listar_calculos(texto="'; DROP TABLE calculos; --") == []
    assert len(bd.listar_calculos()) == 1                              # la tabla sigue existiendo


def test_datos_persisten_al_reabrir_la_base(tmp_path):
    ruta = tmp_path / "persistente.db"
    bd1 = BaseDatos(ruta)
    cid = bd1.guardar_calculo(bd1.crear_proyecto("P"), "c", {"a": 1}, RESUMEN)
    assert BaseDatos(ruta).obtener_calculo(cid)["datos"] == {"a": 1}   # "cerrar y volver a abrir"


def test_nombre_de_proyecto_unico(bd):
    bd.crear_proyecto("Dup")
    with pytest.raises(sqlite3.IntegrityError):
        bd.crear_proyecto("Dup")
