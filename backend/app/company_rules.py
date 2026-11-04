"""Reglas de negocio de la Feature 02. Los valores marcados son supuestos a confirmar (decisión 8)."""

# Supuesto: listas de ejemplo hasta que el profesor entregue las oficiales.
SECTORS = ["Financiero", "Salud", "Manufactura", "Comercio", "Educación", "Tecnología", "Otro"]
SIZES = ["1-10", "11-50", "51-200", "201-1000", "Más de 1000"]

# Supuesto: datos mínimos para pasar al diagnóstico.
REQUIRED_FIELDS = ["name", "nit", "sector", "size_range", "city"]

DOC_TYPES = {
    "plan_estrategico": "Plan estratégico",
    "organigrama": "Organigrama",
    "mapa_procesos": "Mapa de procesos",
    "informe_tecnologia": "Informe de tecnología",
    "politica_datos": "Política de datos personales",
    "operaciones": "Operaciones",
    "inventario_sistemas": "Inventario de sistemas",
    "otro": "Otro",
}
# Supuesto: documentos requeridos (el inventario de sistemas es opcional, 02-R5).
REQUIRED_DOC_TYPES = ["plan_estrategico", "organigrama", "mapa_procesos", "informe_tecnologia", "politica_datos"]
OPTIONAL_DOC_TYPES = ["inventario_sistemas"]
