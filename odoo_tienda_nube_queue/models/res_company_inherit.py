# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResCompanyQueueInherit(models.Model):
    _inherit = "res.company"

    # Queue configuration fields
    tn_queue_enabled = fields.Boolean(
        string='Activar Cola de Sincronización',
        default=False,
        help="Si está activo, los webhooks se encolan para procesamiento asíncrono "
             "en lugar de procesarse inmediatamente."
    )
    tn_queue_batch_size = fields.Integer(
        string='Tamaño del Lote',
        default=50,
        help="Cantidad de registros a procesar por ejecución del cron Worker."
    )
    tn_queue_max_retries = fields.Integer(
        string='Reintentos Máximos',
        default=3,
        help="Número máximo de intentos antes de marcar un registro como error."
    )
    tn_queue_retention_days = fields.Integer(
        string='Días de Retención',
        default=15,
        help="Días que se conservan los registros procesados antes de eliminarlos."
    )
    tn_last_fetch_datetime = fields.Datetime(
        string='Último Fetch',
        help="Fecha y hora del último fetch exitoso desde Tienda Nube. "
             "Se usa como updated_at_min para obtener solo cambios recientes."
    )
