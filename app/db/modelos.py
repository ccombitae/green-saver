from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)

    ciudades: Mapped[list["Ciudad"]] = relationship(back_populates="departamento")


class Ciudad(Base):
    __tablename__ = "ciudades"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamentos.id", ondelete="RESTRICT"), index=True)
    latitud: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    longitud: Mapped[Decimal] = mapped_column(Numeric(8, 5))

    departamento: Mapped[Departamento] = relationship(back_populates="ciudades")


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(40))


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("correo = lower(btrim(correo))", name="ck_usuarios_correo_normalizado"),
        CheckConstraint("consumo_mensual_kwh >= 0", name="ck_usuarios_consumo"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(255), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20))
    contrasena_hash: Mapped[str] = mapped_column(String(255))
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    ciudad_id: Mapped[int | None] = mapped_column(ForeignKey("ciudades.id", ondelete="SET NULL"))
    consumo_mensual_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rol: Mapped[Rol] = relationship(lazy="joined")
    ciudad: Mapped[Ciudad | None] = relationship(lazy="joined")
    calculos: Mapped[list["Calculo"]] = relationship(back_populates="usuario", passive_deletes=True)
    sistema: Mapped["SistemaInstalado | None"] = relationship(back_populates="usuario", passive_deletes=True)

    __mapper_args__ = {"version_id_col": version}


class TipoEquipo(Base):
    __tablename__ = "tipos_equipo"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(40))


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (
        CheckConstraint("potencia_w IS NULL OR potencia_w > 0", name="ck_equipos_potencia"),
        CheckConstraint("capacidad_kwh IS NULL OR capacidad_kwh > 0", name="ck_equipos_capacidad"),
        CheckConstraint("precio_referencia_cop IS NULL OR precio_referencia_cop >= 0", name="ck_equipos_precio"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tipo_equipo_id: Mapped[int] = mapped_column(ForeignKey("tipos_equipo.id", ondelete="RESTRICT"), index=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    potencia_w: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    capacidad_kwh: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    precio_referencia_cop: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    activo: Mapped[bool] = mapped_column(Boolean, server_default="true")

    tipo: Mapped[TipoEquipo] = relationship(lazy="joined")


class Calculo(Base):
    __tablename__ = "calculos"
    __table_args__ = (
        CheckConstraint("consumo_mensual_kwh >= 0", name="ck_calculos_consumo"),
        CheckConstraint("paneles >= 0", name="ck_calculos_paneles"),
        CheckConstraint("cobertura_pct >= 0", name="ck_calculos_cobertura"),
        CheckConstraint("ahorro_estimado_cop >= 0", name="ck_calculos_ahorro"),
        CheckConstraint("estimacion_id IS NULL OR estimacion_id ~ '^[0-9a-f]{24}$'", name="ck_calculos_estimacion"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    ciudad_id: Mapped[int | None] = mapped_column(ForeignKey("ciudades.id", ondelete="RESTRICT"))
    consumo_mensual_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    paneles: Mapped[int] = mapped_column(Integer)
    cobertura_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    ahorro_estimado_cop: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    recomendacion: Mapped[str] = mapped_column(Text, server_default="")
    estimacion_id: Mapped[str | None] = mapped_column(String(24))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario | None] = relationship(back_populates="calculos")
    ciudad: Mapped[Ciudad | None] = relationship()
    cotizaciones: Mapped[list["Cotizacion"]] = relationship(back_populates="calculo", passive_deletes=True)


class EstadoCotizacion(Base):
    __tablename__ = "estados_cotizacion"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(40))


class Cotizacion(Base):
    __tablename__ = "cotizaciones"
    __table_args__ = (CheckConstraint("precio_total >= 0", name="ck_cotizaciones_precio"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    calculo_id: Mapped[int] = mapped_column(ForeignKey("calculos.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    estado_id: Mapped[int] = mapped_column(ForeignKey("estados_cotizacion.id", ondelete="RESTRICT"))
    precio_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    notas: Mapped[str] = mapped_column(Text, server_default="")
    enviada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    aceptada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_instalacion: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, server_default="1")

    calculo: Mapped[Calculo] = relationship(back_populates="cotizaciones")
    cliente: Mapped[Usuario] = relationship(lazy="joined")
    estado: Mapped[EstadoCotizacion] = relationship(lazy="joined")
    detalle: Mapped[list["DetalleCotizacion"]] = relationship(
        back_populates="cotizacion", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )

    __mapper_args__ = {"version_id_col": version}


class DetalleCotizacion(Base):
    __tablename__ = "detalle_cotizacion"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_cantidad"),
        CheckConstraint("precio_unitario_cop IS NULL OR precio_unitario_cop >= 0", name="ck_detalle_precio"),
    )

    cotizacion_id: Mapped[int] = mapped_column(ForeignKey("cotizaciones.id", ondelete="CASCADE"), primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id", ondelete="RESTRICT"), primary_key=True, index=True)
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario_cop: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    cotizacion: Mapped[Cotizacion] = relationship(back_populates="detalle")
    equipo: Mapped[Equipo] = relationship(lazy="joined")


class SistemaInstalado(Base):
    __tablename__ = "sistemas_instalados"
    __table_args__ = (CheckConstraint("potencia_kwp IS NULL OR potencia_kwp > 0", name="ck_sistemas_potencia"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)
    cotizacion_id: Mapped[int | None] = mapped_column(ForeignKey("cotizaciones.id", ondelete="SET NULL"), unique=True)
    potencia_kwp: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    fecha_instalacion: Mapped[date | None] = mapped_column(Date)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario] = relationship(back_populates="sistema")
    equipos: Mapped[list["EquipoSistema"]] = relationship(
        back_populates="sistema", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )


class EquipoSistema(Base):
    __tablename__ = "equipos_sistema"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_equipos_sistema_cantidad"),)

    sistema_id: Mapped[int] = mapped_column(ForeignKey("sistemas_instalados.id", ondelete="CASCADE"), primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id", ondelete="RESTRICT"), primary_key=True, index=True)
    cantidad: Mapped[int] = mapped_column(Integer)

    sistema: Mapped[SistemaInstalado] = relationship(back_populates="equipos")
    equipo: Mapped[Equipo] = relationship(lazy="joined")


class AuditoriaCotizacion(Base):
    __tablename__ = "auditoria_cotizaciones"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cotizacion_id: Mapped[int] = mapped_column(Integer, index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(20))
    estado_nuevo: Mapped[str] = mapped_column(String(20))
    cambiado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usuario_bd: Mapped[str] = mapped_column(Text, server_default=func.current_user())
