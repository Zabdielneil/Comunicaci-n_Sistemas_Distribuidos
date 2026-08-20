import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.database import insertar_registro, listar_registros, contar_registros

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sistema-distribuido")

SERVER_NAME = os.environ["SERVER_NAME"]
PEER_URL = os.environ["PEER_URL"].rstrip("/")

app = FastAPI(title=f"Sistema Distribuido - {SERVER_NAME}")


class RegistroIn(BaseModel):
    dato: str


class RegistroSync(BaseModel):
    id: str
    dato: str
    origen_servidor: str
    creado_en: str


def _fmt(row):
    return {
        "id": str(row[0]),
        "dato": row[1],
        "origen_servidor": row[2],
        "creado_en": row[3].isoformat(),
    }


@app.get("/")
def raiz():
    return {
        "servicio": "Sistema Distribuido de Consulta y Registro de Información",
        "servidor": SERVER_NAME,
        "estado": "disponible",
    }


@app.get("/estado")
async def estado():
    peer_disponible = False
    peer_detalle = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{PEER_URL}/")
            resp.raise_for_status()
            peer_disponible = True
            peer_detalle = resp.json()
    except Exception as exc:
        peer_detalle = f"sin conexión: {exc.__class__.__name__}"

    return {
        "servidor": SERVER_NAME,
        "hora_servidor": datetime.now(timezone.utc).isoformat(),
        "total_registros_locales": contar_registros(),
        "servidor_par": {
            "url": PEER_URL,
            "disponible": peer_disponible,
            "detalle": peer_detalle,
        },
    }


@app.post("/registrar")
async def registrar(payload: RegistroIn):
    nuevo_id = str(uuid.uuid4())
    row = insertar_registro(nuevo_id, payload.dato, SERVER_NAME)
    if row is None:
        raise HTTPException(status_code=500, detail="No se pudo registrar el dato")
    registro = _fmt(row)

    sincronizado = False
    error_sync = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(f"{PEER_URL}/sincronizar", json=registro)
            resp.raise_for_status()
            sincronizado = True
    except Exception as exc:
        error_sync = f"{exc.__class__.__name__}: {exc}"
        log.warning("No se pudo sincronizar con %s: %s", PEER_URL, error_sync)

    return {
        "mensaje": "Registro almacenado",
        "atendido_por": SERVER_NAME,
        "registro": registro,
        "sincronizado_con_par": sincronizado,
        "error_sincronizacion": error_sync,
    }


@app.get("/consultar")
def consultar():
    filas = listar_registros()
    return {
        "atendido_por": SERVER_NAME,
        "total": len(filas),
        "registros": [_fmt(f) for f in filas],
    }


@app.post("/sincronizar")
def sincronizar(payload: RegistroSync):
    row = insertar_registro(
        payload.id, payload.dato, payload.origen_servidor, payload.creado_en
    )
    if row is None:
        return {
            "mensaje": "Registro ya existente, sin cambios",
            "servidor": SERVER_NAME,
            "id": payload.id,
        }
    return {
        "mensaje": "Registro sincronizado correctamente",
        "servidor": SERVER_NAME,
        "registro": _fmt(row),
    }


async def _reconciliar_una_vez() -> int:
    """Trae del par todo lo que este servidor no tenga y lo inserta localmente.
    Devuelve la cantidad de registros nuevos incorporados."""
    nuevos = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{PEER_URL}/consultar")
        resp.raise_for_status()
        data = resp.json()

    for r in data.get("registros", []):
        fila = insertar_registro(r["id"], r["dato"], r["origen_servidor"], r["creado_en"])
        if fila is not None:
            nuevos += 1
    return nuevos


async def _bucle_reconciliacion():
    """Se ejecuta en segundo plano durante toda la vida del contenedor.
    Reintenta cada 15s: si el par está caído, no pasa nada (se reintenta luego);
    en cuanto el par vuelve a responder, se recupera automáticamente todo lo perdido."""
    while True:
        try:
            nuevos = await _reconciliar_una_vez()
            if nuevos:
                log.info("Reconciliación: %d registro(s) recuperado(s) del par", nuevos)
        except Exception as exc:
            log.debug("Par no disponible para reconciliar (%s), reintentando...", exc.__class__.__name__)
        await asyncio.sleep(15)


@app.on_event("startup")
async def iniciar_reconciliacion():
    asyncio.create_task(_bucle_reconciliacion())
