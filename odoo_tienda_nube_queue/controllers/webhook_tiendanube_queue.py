# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request
from odoo.addons.odoo_tienda_nube.controllers.webhook_tiendanube import TiendaNubeWebHook

_logger = logging.getLogger(__name__)


class TiendaNubeWebHookQueue(TiendaNubeWebHook):
    """
    Extends the base TiendaNubeWebHook controller to support queue-based processing.
    When queue is enabled for a company, webhooks are added to the queue instead of
    being processed immediately.
    """

    @http.route('/webhook_tn/<string:code_event>', auth='public', cors='*', csrf=False)
    def TiendaNubeWebHook(self, **kw):
        """
        Override the webhook endpoint to support queue-based processing.
        If queue is enabled, creates a queue record and returns HTTP 202.
        Otherwise, falls back to the original processing.
        """
        try:
            data = json.loads(request.httprequest.get_data())
        except (json.JSONDecodeError, Exception) as e:
            _logger.error("Error parsing webhook data: %s", str(e))
            return request.make_response(
                json.dumps({"mensaje": "Error al parsear datos"}),
                headers={'Content-Type': 'application/json'},
                status=400
            )

        # Get the webhook and company
        code_event = kw.get('code_event', '')
        webhook = request.env['webhook.tn'].sudo().search([
            ('url', '=', request.env['ir.config_parameter'].sudo().get_param('web.base.url') + '/webhook_tn/' + code_event)
        ], limit=1)

        company = webhook.company_id if webhook and webhook.company_id else None

        # Check if queue is enabled for this company
        if company and company.tn_queue_enabled:
            return self._process_with_queue(data, company, webhook)

        # Fall back to original processing
        return super().TiendaNubeWebHook(**kw)

    def _process_with_queue(self, data, company, webhook):
        """
        Process webhook by adding to queue instead of immediate processing.
        """
        # Check for duplicates using parent method
        if self.duplicity_check(data):
            return request.make_response(
                json.dumps({"mensaje": "Operación duplicada"}),
                headers={'Content-Type': 'application/json'},
                status=200
            )

        # Create webhook.tn.received record
        request.env['webhook.tn.received'].sudo().create({
            'name': 'Evento: ' + data['event'] + ' - ID: ' + str(data['id']) + ' - Store ID:' + str(data['store_id']),
            'id_event_tn': data['id'],
            'event': data['event'],
            'store_id': data['store_id'],
        })

        # Create queue record
        event = webhook.event if webhook else data.get('event', '')
        queue_record = request.env['tiendanube.sync.queue'].sudo().create_from_webhook(
            webhook_data=data,
            company=company,
            event=event
        )

        if queue_record:
            _logger.info("Webhook queued successfully: %s (ID: %s)", event, queue_record.id)
            return request.make_response(
                json.dumps({
                    "mensaje": "Webhook encolado para procesamiento",
                    "queue_id": queue_record.id
                }),
                headers={'Content-Type': 'application/json'},
                status=202  # Accepted
            )
        else:
            _logger.warning("Failed to queue webhook: %s", event)
            return request.make_response(
                json.dumps({"mensaje": "Error al encolar webhook"}),
                headers={'Content-Type': 'application/json'},
                status=500
            )
