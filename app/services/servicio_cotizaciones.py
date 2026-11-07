from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.db.database import sesion_lectura, sesion_transaccional
from app.db.modelos import Calculo, Cotizacion, DetalleCotizacion, Equipo, EstadoCotizacion, TipoEquipo, Usuario
from app.schemas.quotes import QuoteSendRequest
from app.services.servicio_autenticacion import normalizar_correo
from app.services.servicio_calculos import calculos_para_cotizar
from app.services.servicio_correo import construir_mensaje, enviar_correo
from app.services.servicio_sistemas import sistema_de_usuario

SIN_BATERIA = "Sin bateria"
CAMPO_POR_TIPO = {"panel": "panelType", "inversor": "inverterType", "bateria": "batteryType", "estructura": "structureType"}
LISTA_POR_TIPO = {"panel": "panelTypes", "inversor": "inverterTypes", "bateria": "batteryTypes", "estructura": "structureTypes"}


def mensaje_de_error_bd(error: DBAPIError) -> str:
    diagnostico = getattr(error.orig, "diag", None)
    return (getattr(diagnostico, "message_primary", None) or str(error.orig)).strip()


def materiales_de(cotizacion: Cotizacion) -> dict:
    materiales = {campo: "" for campo in CAMPO_POR_TIPO.values()}
    materiales["batteryType"] = SIN_BATERIA
    for linea in cotizacion.detalle:
        materiales[CAMPO_POR_TIPO[linea.equipo.tipo.codigo]] = linea.equipo.nombre
    return materiales


def a_diccionario(cotizacion: Cotizacion) -> dict:
    return {
        "id": cotizacion.id,
        "calculation_id": cotizacion.calculo_id,
        "client_email": cotizacion.cliente.correo,
        "client_name": cotizacion.cliente.nombre,
        "total_price": cotizacion.precio_total,
        "notes": cotizacion.notas,
        "materials": materiales_de(cotizacion),
        "items": [
            {
                "equipment": linea.equipo.nombre,
                "type": linea.equipo.tipo.codigo,
                "quantity": linea.cantidad,
                "unitPriceCop": linea.precio_unitario_cop,
            }
            for linea in cotizacion.detalle
        ],
        "status": cotizacion.estado.codigo,
        "sent_at": cotizacion.enviada_en,
        "accepted_at": cotizacion.aceptada_en,
        "installation_date": cotizacion.fecha_instalacion.isoformat() if cotizacion.fecha_instalacion else None,
        "version": cotizacion.version,
    }


def opciones_de_cotizacion() -> dict:
    opciones = {lista: [] for lista in LISTA_POR_TIPO.values()}
    with sesion_lectura() as sesion:
        consulta = (
            select(TipoEquipo.codigo, Equipo.nombre)
            .join(TipoEquipo, TipoEquipo.id == Equipo.tipo_equipo_id)
            .where(Equipo.activo.is_(True))
            .order_by(TipoEquipo.id, Equipo.id)
        )
        for tipo, nombre in sesion.execute(consulta):
            opciones[LISTA_POR_TIPO[tipo]].append(nombre)
    opciones["batteryTypes"].append(SIN_BATERIA)
    return opciones


def calculos_cotizables() -> list[dict]:
    return calculos_para_cotizar()


def listar_cotizaciones() -> list[dict]:
    with sesion_lectura() as sesion:
        cotizaciones = sesion.scalars(select(Cotizacion).order_by(Cotizacion.enviada_en.desc(), Cotizacion.id.desc())).all()
        return [a_diccionario(c) for c in cotizaciones]


def equipo_por_nombre(sesion, tipo: str, nombre: str) -> Equipo:
    equipo = sesion.scalar(
        select(Equipo)
        .join(TipoEquipo, TipoEquipo.id == Equipo.tipo_equipo_id)
        .where(TipoEquipo.codigo == tipo, func.lower(Equipo.nombre) == nombre.strip().lower())
    )
    if equipo is None:
        raise ValueError(f"El equipo '{nombre}' no está en el catálogo")
    return equipo


def estado(sesion, codigo: str) -> EstadoCotizacion:
    return sesion.scalar(select(EstadoCotizacion).where(EstadoCotizacion.codigo == codigo))


def registrar_cotizacion(datos: QuoteSendRequest) -> dict:
    with sesion_transaccional() as sesion:
        calculo = sesion.get(Calculo, datos.calculationId)
        if calculo is None:
            raise ValueError("El calculo seleccionado no existe")
        cliente = sesion.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(datos.clientEmail)))
        if cliente is None:
            raise ValueError("El cliente debe tener una cuenta registrada en Green Saver")

        cotizacion = Cotizacion(
            calculo=calculo,
            cliente=cliente,
            estado=estado(sesion, "pending"),
            precio_total=Decimal(str(datos.totalPrice)),
            notas=datos.notes,
        )
        sesion.add(cotizacion)
        materiales = datos.materials.model_dump()
        for tipo, campo in CAMPO_POR_TIPO.items():
            nombre = (materiales.get(campo) or "").strip()
            if not nombre or (tipo == "bateria" and nombre.lower() == SIN_BATERIA.lower()):
                continue
            equipo = equipo_por_nombre(sesion, tipo, nombre)
            cotizacion.detalle.append(
                DetalleCotizacion(
                    equipo=equipo,
                    cantidad=max(calculo.paneles, 1) if tipo == "panel" else 1,
                    precio_unitario_cop=equipo.precio_referencia_cop,
                )
            )
        sesion.flush()
        return {
            "id": cotizacion.id,
            "calculo_id": calculo.id,
            "correo": cliente.correo,
            "nombre": cliente.nombre,
            "materiales": materiales_de(cotizacion),
            "enviada_en": cotizacion.enviada_en,
        }


def cambiar_estado(cotizacion_id: int, codigo: str) -> None:
    with sesion_transaccional() as sesion:
        cotizacion = sesion.get(Cotizacion, cotizacion_id)
        cotizacion.estado = estado(sesion, codigo)


def enviar_cotizacion(datos: QuoteSendRequest) -> dict:
    registrada = registrar_cotizacion(datos)
    estado_final, error_envio = "sent", None
    try:
        enviar_correo(
            construir_mensaje(
                registrada["correo"], registrada["nombre"], registrada["calculo_id"],
                registrada["materiales"], datos.totalPrice, datos.notes,
            )
        )
    except Exception as error:
        estado_final, error_envio = "failed", str(error)
    cambiar_estado(registrada["id"], estado_final)

    respuesta = {
        "id": registrada["id"],
        "calculationId": registrada["calculo_id"],
        "clientEmail": registrada["correo"],
        "status": estado_final,
        "sentAt": registrada["enviada_en"].isoformat(),
    }
    if error_envio:
        respuesta["emailError"] = error_envio
    return respuesta


def aceptar_cotizacion(cotizacion_id: int, fecha_instalacion: str) -> dict:
    try:
        fecha = date.fromisoformat(fecha_instalacion.strip()[:10])
    except ValueError as error:
        raise ValueError("La fecha de instalación debe tener el formato AAAA-MM-DD") from error

    try:
        with sesion_transaccional() as sesion:
            sistema_id = sesion.execute(
                text("CALL aceptar_cotizacion(:cotizacion, :fecha, NULL)"),
                {"cotizacion": cotizacion_id, "fecha": fecha},
            ).scalar_one()
            cliente_id = sesion.scalar(select(Cotizacion.cliente_id).where(Cotizacion.id == cotizacion_id))
    except DBAPIError as error:
        raise ValueError(mensaje_de_error_bd(error)) from error

    return {
        "quoteId": cotizacion_id,
        "status": "accepted",
        "installDate": fecha.isoformat(),
        "systemId": sistema_id,
        "system": sistema_de_usuario(cliente_id),
    }
