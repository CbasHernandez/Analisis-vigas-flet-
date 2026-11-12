"""Acceso a datos con SQLite. Todo el SQL de la aplicación vive en este archivo.

Esquema (2 tablas relacionadas por llave foránea):
    proyectos(id, nombre UNIQUE, descripcion, creado)
    calculos(id, proyecto_id -> proyectos.id ON DELETE CASCADE, nombre, creado,
             datos_json, momento_max_kNm, cortante_max_kN, flecha_max_mm,
             esfuerzo_max_MPa, cumple)

Todas las consultas usan parámetros (?) y nunca concatenan texto del usuario.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # carpeta del proyecto (ruta relativa al código)
RUTA_BD_DEFECTO = RAIZ / "datos" / "proyectos.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS proyectos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL DEFAULT '',
    creado      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calculos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id      INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    nombre           TEXT NOT NULL,
    creado           TEXT NOT NULL,
    datos_json       TEXT NOT NULL,
    momento_max_kNm  REAL NOT NULL,
    cortante_max_kN  REAL NOT NULL,
    flecha_max_mm    REAL NOT NULL,
    esfuerzo_max_MPa REAL NOT NULL,
    cumple           INTEGER NOT NULL CHECK (cumple IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_calculos_proyecto ON calculos(proyecto_id);
"""


def _ahora() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class BaseDatos:
    """Encapsula la conexión y las operaciones CRUD de proyectos y cálculos."""

    def __init__(self, ruta: Path | str = RUTA_BD_DEFECTO):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as con:
            con.executescript(ESQUEMA)                  # CREATE TABLE IF NOT EXISTS

    def _conexion(self):
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")         # SQLite no las activa por defecto
        return _Transaccion(con)

    # ---------------- proyectos ----------------
    def crear_proyecto(self, nombre: str, descripcion: str = "") -> int:
        with self._conexion() as con:
            cur = con.execute("INSERT INTO proyectos (nombre, descripcion, creado) VALUES (?, ?, ?)",
                              (nombre.strip(), descripcion.strip(), _ahora()))
            return cur.lastrowid

    def listar_proyectos(self) -> list[sqlite3.Row]:
        with self._conexion() as con:
            return con.execute(
                """SELECT p.*, COUNT(c.id) AS n_calculos FROM proyectos p
                   LEFT JOIN calculos c ON c.proyecto_id = p.id
                   GROUP BY p.id ORDER BY p.nombre COLLATE NOCASE""").fetchall()

    def obtener_o_crear_proyecto(self, nombre: str) -> int:
        """Devuelve el id del proyecto con ese nombre; lo crea si no existe."""
        with self._conexion() as con:
            fila = con.execute("SELECT id FROM proyectos WHERE nombre = ?", (nombre.strip(),)).fetchone()
        return fila["id"] if fila else self.crear_proyecto(nombre)

    def eliminar_proyecto(self, proyecto_id: int) -> None:
        """Elimina el proyecto y (por ON DELETE CASCADE) todos sus cálculos."""
        with self._conexion() as con:
            con.execute("DELETE FROM proyectos WHERE id = ?", (proyecto_id,))

    # ---------------- cálculos ----------------
    def guardar_calculo(self, proyecto_id: int, nombre: str, datos: dict, resumen: dict) -> int:
        with self._conexion() as con:
            cur = con.execute(
                """INSERT INTO calculos (proyecto_id, nombre, creado, datos_json, momento_max_kNm,
                       cortante_max_kN, flecha_max_mm, esfuerzo_max_MPa, cumple)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (proyecto_id, nombre.strip(), _ahora(), json.dumps(datos),
                 resumen["momento_max_kNm"], resumen["cortante_max_kN"], resumen["flecha_max_mm"],
                 resumen["esfuerzo_max_MPa"], int(resumen["cumple"])))
            return cur.lastrowid

    def listar_calculos(self, texto: str = "", proyecto_id: int | None = None) -> list[sqlite3.Row]:
        """Lista cálculos; filtra por texto (en el nombre del cálculo o del proyecto) y/o proyecto."""
        consulta = """SELECT c.id, c.nombre, c.creado, c.momento_max_kNm, c.cortante_max_kN,
                             c.flecha_max_mm, c.esfuerzo_max_MPa, c.cumple,
                             p.id AS proyecto_id, p.nombre AS proyecto
                      FROM calculos c JOIN proyectos p ON p.id = c.proyecto_id
                      WHERE (c.nombre LIKE ? OR p.nombre LIKE ?)"""
        params: list = [f"%{texto.strip()}%"] * 2
        if proyecto_id is not None:
            consulta += " AND p.id = ?"
            params.append(proyecto_id)
        with self._conexion() as con:
            return con.execute(consulta + " ORDER BY c.id DESC", params).fetchall()

    def obtener_calculo(self, calculo_id: int) -> dict | None:
        """Devuelve el cálculo con sus datos de entrada ya convertidos a dict, o None."""
        with self._conexion() as con:
            fila = con.execute(
                """SELECT c.*, p.nombre AS proyecto, p.descripcion AS proyecto_descripcion
                   FROM calculos c JOIN proyectos p ON p.id = c.proyecto_id WHERE c.id = ?""",
                (calculo_id,)).fetchone()
        if fila is None:
            return None
        resultado = dict(fila)
        resultado["datos"] = json.loads(resultado.pop("datos_json"))
        return resultado

    def renombrar_calculo(self, calculo_id: int, nuevo_nombre: str) -> None:
        with self._conexion() as con:
            con.execute("UPDATE calculos SET nombre = ? WHERE id = ?", (nuevo_nombre.strip(), calculo_id))

    def eliminar_calculo(self, calculo_id: int) -> None:
        with self._conexion() as con:
            con.execute("DELETE FROM calculos WHERE id = ?", (calculo_id,))


class _Transaccion:
    """Administrador de contexto: confirma (commit) si todo sale bien, revierte si hay error y siempre cierra."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def __enter__(self) -> sqlite3.Connection:
        return self.con

    def __exit__(self, tipo, valor, traza) -> None:
        with closing(self.con):
            if tipo is None:
                self.con.commit()
            else:
                self.con.rollback()
