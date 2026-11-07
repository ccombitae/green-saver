use("green_saver");

db.estimaciones.find(
  { "ciudad.id": "girardot" },
  { creado_en: 1, "solicitud.consumo_mensual_kwh": 1, "resumen.paneles": 1, "resumen.costo_total_cop": 1 }
).sort({ creado_en: -1 }).limit(5);

db.estimaciones.find({ "detalle_mensual": { $elemMatch: { cobertura_pct: { $lt: 90 } } } }, { "ciudad.nombre": 1, "resumen": 1 });

db.estimaciones.aggregate([
  { $group: {
      _id: "$ciudad.id",
      ciudad: { $first: "$ciudad.nombre" },
      estimaciones: { $sum: 1 },
      consumo_promedio_kwh: { $avg: "$solicitud.consumo_mensual_kwh" },
      paneles_promedio: { $avg: "$resumen.paneles" },
      costo_promedio_cop: { $avg: "$resumen.costo_total_cop" } } },
  { $sort: { estimaciones: -1 } }
]);

db.estimaciones.aggregate([
  { $unwind: "$detalle_mensual" },
  { $group: { _id: "$detalle_mensual.mes", generacion_promedio_kwh: { $avg: "$detalle_mensual.generacion_kwh" } } },
  { $sort: { generacion_promedio_kwh: 1 } },
  { $limit: 3 }
]);

db.estimaciones.find({ "ciudad.id": "girardot" }).sort({ creado_en: -1 }).explain("executionStats");

db.estimaciones.getIndexes();
