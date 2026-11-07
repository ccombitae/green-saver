import re
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.db.database import sesion_lectura, sesion_transaccional
from app.db.modelos import Equipo, EquipoSistema, SistemaInstalado, TipoEquipo, Usuario
from app.schemas.systems import SystemAssignRequest
from app.services.servicio_autenticacion import normalizar_correo

PANEL_SIN_ESPECIFICAR = "Panel solar sin especificar"


def formato_numero(valor: Decimal) -> str:
    return f"{valor:f}".rstrip("0").rstrip(".")


def a_diccionario(sistema: SistemaInstalado) -> dict:
    por_tipo = {"panel": [], "inversor": [], "bateria": [], "estructura": []}
    for linea in sistema.equipos:
        por_tipo[linea.equipo.tipo.codigo].append(linea)
    paneles = sum(linea.cantidad for linea in por_tipo["panel"])
    return {
        "id": sistema.id,
        "userId": sistema.usuario_id,
        "email": sistema.usuario.correo,
        "name": sistema.usuario.nombre,
        "capacity": f"{formato_numero(sistema.potencia_kwp)} kWp" if sistema.potencia_kwp else "",
        "panels": f"{paneles} paneles" if paneles else "",
        "panelType": ", ".join(l.equipo.nombre for l in por_tipo["panel"] if l.equipo.nombre != PANEL_SIN_ESPECIFICAR),
        "inverter": ", ".join(l.equipo.nombre for l in por_tipo["inversor"]),
        "battery": ", ".join(l.equipo.nombre for l in por_tipo["bateria"]),
        "structureType": ", ".join(l.equipo.nombre for l in por_tipo["estructura"]),
        "installDate": sistema.fecha_instalacion.isoformat() if sistema.fecha_instalacion else "",
        "sourceQuoteId": sistema.cotizacion_id,
        "createdAt": sistema.creado_en.isoformat(),
        "updatedAt": sistema.actualizado_en.isoformat(),
    }


def sistema_de_usuario(usuario_id: int) -> dict | None:
    with sesion_lectura() as sesion:
        sistema = sesion.scalar(select(SistemaInstalado).where(SistemaInstalado.usuario_id == usuario_id))
        return a_diccionario(sistema) if sistema else None


def listar_sistemas(correo: str | None = None) -> list[dict]:
    consulta = select(SistemaInstalado).join(Usuario, Usuario.id == SistemaInstalado.usuario_id)
    if correo:
        consulta = consulta.where(Usuario.correo == normalizar_correo(correo))
    with sesion_lectura() as sesion:
        sistemas = sesion.scalars(consulta.order_by(SistemaInstalado.actualizado_en.desc())).all()
        return [a_diccionario(s) for s in sistemas]


def primer_numero(texto: str) -> Decimal | None:
    coincidencia = re.search(r"\d+(?:[.,]\d+)?", texto or "")
    return Decimal(coincidencia.group().replace(",", ".")) if coincidencia else None


def equipo_o_nuevo(sesion, tipo: str, nombre: str) -> Equipo:
    equipo = sesion.scalar(
        select(Equipo)
        .join(TipoEquipo, TipoEquipo.id == Equipo.tipo_equipo_id)
        .where(TipoEquipo.codigo == tipo, func.lower(Equipo.nombre) == nombre.lower())
    )
    if equipo is None:
        tipo_equipo = sesion.scalar(select(TipoEquipo).where(TipoEquipo.codigo == tipo))
        equipo = Equipo(tipo=tipo_equipo, nombre=nombre, activo=False)
        sesion.add(equipo)
        sesion.flush()
    return equipo


def asignar_sistema(datos: SystemAssignRequest) -> dict:
    sistema_recibido = datos.system
    fecha = None
    if sistema_recibido.installDate.strip():
        try:
            fecha = date.fromisoformat(sistema_recibido.installDate.strip()[:10])
        except ValueError as error:
            raise ValueError("La fecha de instalación debe tener el formato AAAA-MM-DD") from error

    with sesion_transaccional() as sesion:
        usuario = sesion.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(datos.email)))
        if usuario is None:
            raise ValueError("El usuario no existe")

        sistema = sesion.scalar(select(SistemaInstalado).where(SistemaInstalado.usuario_id == usuario.id).with_for_update())
        if sistema is None:
            sistema = SistemaInstalado(usuario=usuario)
            sesion.add(sistema)
        potencia = primer_numero(sistema_recibido.capacity)
        sistema.potencia_kwp = potencia if potencia else None
        sistema.fecha_instalacion = fecha
        sistema.cotizacion_id = None
        sistema.equipos.clear()
        sesion.flush()

        cantidad_paneles = int(primer_numero(sistema_recibido.panels) or 0)
        if cantidad_paneles > 0:
            sistema.equipos.append(EquipoSistema(equipo=equipo_o_nuevo(sesion, "panel", PANEL_SIN_ESPECIFICAR), cantidad=cantidad_paneles))
        for tipo, nombre in (("inversor", sistema_recibido.inverter), ("bateria", sistema_recibido.battery)):
            nombre = (nombre or "").strip()
            if nombre and nombre.lower() != "sin bateria":
                sistema.equipos.append(EquipoSistema(equipo=equipo_o_nuevo(sesion, tipo, nombre), cantidad=1))
        sesion.flush()
        sesion.refresh(sistema)
        return a_diccionario(sistema)
