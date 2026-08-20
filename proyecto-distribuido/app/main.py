izado_con_par": sincronizado,
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
