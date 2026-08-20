import os
from contextlib import contextmanager
from psycopg2 import pool

DATABASE_URL = os.environ["DATABASE_URL"]

_pool = pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL)


@contextmanager
def get_conn():
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def insertar_registro(id_, dato, origen_servidor, creado_en=None):
    """Inserta un registro. Si ya existe el id (sincronización), no hace nada."""
    with get_conn() as conn:
        cur = conn.cursor()
        if creado_en is None:
            cur.execute(
                """INSERT INTO registros (id, dato, origen_servidor)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO NOTHING
                   RETURNING id, dato, origen_servidor, creado_en""",
                (id_, dato, origen_servidor),
            )
        else:
            cur.execute(
                """INSERT INTO registros (id, dato, origen_servidor, creado_en)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO NOTHING
                   RETURNING id, dato, origen_servidor, creado_en""",
                (id_, dato, origen_servidor, creado_en),
            )
        row = cur.fetchone()
        cur.close()
        return row


def listar_registros():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, dato, origen_servidor, creado_en
               FROM registros ORDER BY creado_en DESC"""
        )
        rows = cur.fetchall()
        cur.close()
        return rows


def contar_registros():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM registros")
        total = cur.fetchone()[0]
        cur.close()
        return total
