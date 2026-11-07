from datetime import date
from decimal import Decimal

from sqlalchemy import select, text

from app.db.database import sesion_lectura, sesion_transaccional
from app.db.modelos import Calculo, Ciudad, Usuario
from app.schemas.solar import CalculoCrear
from app.services.servicio_autenticacion import normalizar_correo


def consulta_calculos():
    return (
        select(
            Calculo.id,
            Usuario.correo,
            Usuario.nombre,
            Calculo.consumo_mensual_kwh,
            Calculo.paneles,
            Calculo.cobertura_pct,
            Calculo.ahorro_estimado_cop,
            Calculo.recomendacion,
            Calculo.creado_en,
            Ciudad.codigo.label("ciudad_codigo"),
            Calculo.estimacion_id,
        )
        .outerjoin(Usuario, Usuario.id == Calculo.usuario_id)
        .outerjoin(Ciudad, Ciudad.id == Calculo.ciudad_id)
        .order_by(Calculo.creado_en.desc(), Calculo.id.desc())
    )


def fila_a_diccionario(fila) -> dict:
    return {
        "id": fila.id,
        "email": fila.correo,
        "consumption": fila.consumo_mensual_kwh,
        "estimatedPanels": fila.paneles,
        "coverage": fila.cobertura_pct,
        "estimatedSavings": fila.ahorro_estimado_cop,
        "recommendation": fila.recomendacion,
        "created_at": fila.creado_en,
        "cityId": fila.ciudad_codigo,
        "estimationId": fila.estimacion_id,
    }


def listar_calculos(correo: str | None = None) -> list[dict]:
    consulta = consulta_calculos()
    if correo:
        consulta = consulta.where(Usuario.correo == normalizar_correo(correo))
    with sesion_lectura() as sesion:
        return [fila_a_diccionario(f) for f in sesion.execute(consulta)]


def crear_calculo(datos: CalculoCrear, correo_token: str | None = None, es_administrador: bool = False) -> dict:
    correo = normalizar_correo(datos.email if es_administrador or not correo_token else correo_token)
    with sesion_transaccional() as sesion:
        usuario = sesion.scalar(select(Usuario).where(Usuario.correo == correo))
        if usuario is None:
            raise ValueError("El cálculo debe pertenecer a un usuario registrado")
        ciudad = None
        if datos.cityId:
            ciudad = sesion.scalar(select(Ciudad).where(Ciudad.codigo == datos.cityId.strip().lower()))
            if ciudad is None:
                raise ValueError(f"La ciudad '{datos.cityId}' no está en el catálogo")
        calculo = Calculo(
            usuario=usuario,
            ciudad=ciudad,
            consumo_mensual_kwh=Decimal(str(datos.consumption)),
            paneles=datos.estimatedPanels,
            cobertura_pct=Decimal(str(round(datos.coverage, 2))),
            ahorro_estimado_cop=Decimal(str(round(datos.estimatedSavings, 2))),
            recomendacion=datos.recommendation,
            estimacion_id=datos.estimationId,
        )
        sesion.add(calculo)
        sesion.flush()
        sesion.refresh(calculo)
        return {
            "id": calculo.id,
            "email": usuario.correo,
            "consumption": datos.consumption,
            "estimatedPanels": datos.estimatedPanels,
            "coverage": datos.coverage,
            "estimatedSavings": datos.estimatedSavings,
            "recommendation": datos.recommendation,
            "created_at": calculo.creado_en.isoformat(),
            "cityId": ciudad.codigo if ciudad else None,
            "estimationId": calculo.estimacion_id,
        }


def eliminar_calculo(calculo_id: int) -> dict:
    with sesion_transaccional() as sesion:
        calculo = sesion.get(Calculo, calculo_id)
        if calculo is None:
            raise ValueError("El cálculo no existe")
        sesion.delete(calculo)
    return {"message": "Cálculo eliminado"}


def reporte_general() -> list[dict]:
    with sesion_lectura() as sesion:
        return [
            {
                "id": f.id,
                "nombre": f.nombre or f.correo,
                "email": f.correo,
                "consumption": f.consumo_mensual_kwh,
                "estimatedpanels": f.paneles,
                "coverage": f.cobertura_pct,
                "estimatedsavings": f.ahorro_estimado_cop,
                "recommendation": f.recomendacion,
                "created_at": f.creado_en,
            }
            for f in sesion.execute(consulta_calculos())
        ]


def calculos_para_cotizar() -> list[dict]:
    with sesion_lectura() as sesion:
        return [
            {
                "id": f.id,
                "email": f.correo,
                "client_name": f.nombre or f.correo,
                "consumption": f.consumo_mensual_kwh,
                "estimatedpanels": f.paneles,
                "coverage": f.cobertura_pct,
                "estimatedsavings": f.ahorro_estimado_cop,
                "recommendation": f.recomendacion,
                "created_at": f.creado_en,
            }
            for f in sesion.execute(consulta_calculos().where(Calculo.usuario_id.is_not(None)))
        ]


def estadisticas_mensuales(desde: date, hasta: date) -> list[dict]:
    if hasta < desde:
        raise ValueError("La fecha final no puede ser anterior a la inicial")
    with sesion_lectura() as sesion:
        filas = sesion.execute(
            text("SELECT mes, calculos, paneles_promedio, ahorro_total_cop FROM fn_estadisticas_mensuales(:desde, :hasta)"),
            {"desde": desde, "hasta": hasta},
        )
        return [dict(f._mapping) for f in filas]
