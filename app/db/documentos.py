import logging
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

from app.core.config import settings

registro = logging.getLogger("green_saver.mongo")
_clientes: dict[str, MongoClient] = {}
_colecciones_preparadas: set[str] = set()


def coleccion_estimaciones() -> Collection | None:
    url = settings.mongo_url
    if not url:
        return None
    if url not in _clientes:
        _clientes[url] = MongoClient(url, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, tz_aware=True, appname="green-saver-api")
    coleccion = _clientes[url][settings.mongo_bd]["estimaciones"]
    llave = f"{url}/{settings.mongo_bd}"
    if llave not in _colecciones_preparadas:
        coleccion.create_index([("ciudad.id", ASCENDING), ("creado_en", DESCENDING)], name="ix_ciudad_fecha")
        coleccion.create_index([("creado_en", DESCENDING)], name="ix_fecha")
        coleccion.create_index([("usuario", ASCENDING), ("creado_en", DESCENDING)], name="ix_usuario_fecha", sparse=True)
        _colecciones_preparadas.add(llave)
    return coleccion


def guardar_estimacion(solicitud: dict, resultado: dict, usuario: str | None = None) -> str | None:
    try:
        coleccion = coleccion_estimaciones()
        if coleccion is None:
            return None
        documento = {
            "creado_en": datetime.now(timezone.utc),
            "usuario": usuario,
            "ciudad": resultado.get("ciudad"),
            "solicitud": solicitud,
            "resumen": {
                "paneles": resultado["paneles"],
                "potencia_kwp": resultado["potencia_kwp"],
                "cobertura_anual_pct": resultado["cobertura_anual_pct"],
                "ahorro_anual_cop": resultado["ahorro_anual_cop"],
                "costo_total_cop": (resultado.get("costos") or {}).get("total_cop"),
                "fuente_hsp": resultado.get("fuente_hsp"),
            },
            "detalle_mensual": resultado.get("detalle_mensual", []),
            "equipos": {
                "inversor": resultado.get("inversor"),
                "baterias": resultado.get("baterias"),
                "instalacion": resultado.get("instalacion"),
            },
            "costos": resultado.get("costos"),
        }
        return str(coleccion.insert_one(documento).inserted_id)
    except Exception as error:
        registro.warning("No se pudo guardar la estimación en MongoDB: %s", error)
        return None


def serializar(documento: dict) -> dict:
    documento = dict(documento)
    documento["id"] = str(documento.pop("_id"))
    return documento


def obtener_estimacion(identificador: str) -> dict | None:
    coleccion = coleccion_estimaciones()
    if coleccion is None:
        raise RuntimeError("MongoDB no está configurado (MONGO_URL)")
    try:
        llave = ObjectId(identificador)
    except InvalidId:
        return None
    documento = coleccion.find_one({"_id": llave})
    return serializar(documento) if documento else None


def estimaciones_recientes(usuario: str | None = None, limite: int = 20) -> list[dict]:
    coleccion = coleccion_estimaciones()
    if coleccion is None:
        raise RuntimeError("MongoDB no está configurado (MONGO_URL)")
    filtro = {"usuario": usuario} if usuario else {}
    proyeccion = {"detalle_mensual": 0, "equipos": 0, "costos": 0}
    cursor = coleccion.find(filtro, proyeccion).sort("creado_en", DESCENDING).limit(limite)
    return [serializar(d) for d in cursor]


def estadisticas_por_ciudad(desde: datetime | None = None) -> list[dict]:
    coleccion = coleccion_estimaciones()
    if coleccion is None:
        raise RuntimeError("MongoDB no está configurado (MONGO_URL)")
    etapas = []
    if desde:
        etapas.append({"$match": {"creado_en": {"$gte": desde}}})
    etapas += [
        {
            "$group": {
                "_id": "$ciudad.id",
                "ciudad": {"$first": "$ciudad.nombre"},
                "estimaciones": {"$sum": 1},
                "consumo_promedio_kwh": {"$avg": "$solicitud.consumo_mensual_kwh"},
                "paneles_promedio": {"$avg": "$resumen.paneles"},
                "costo_promedio_cop": {"$avg": "$resumen.costo_total_cop"},
                "ultima": {"$max": "$creado_en"},
            }
        },
        {"$sort": {"estimaciones": -1, "_id": 1}},
        {
            "$project": {
                "_id": 0,
                "ciudad_id": "$_id",
                "ciudad": 1,
                "estimaciones": 1,
                "consumo_promedio_kwh": {"$round": ["$consumo_promedio_kwh", 1]},
                "paneles_promedio": {"$round": ["$paneles_promedio", 2]},
                "costo_promedio_cop": {"$round": ["$costo_promedio_cop", 0]},
                "ultima": 1,
            }
        },
    ]
    return list(coleccion.aggregate(etapas))
