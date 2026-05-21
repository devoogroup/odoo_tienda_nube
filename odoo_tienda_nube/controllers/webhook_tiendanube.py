# -*- coding: utf-8 -*-
import logging
import requests

import odoo
import json
from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)
CORS = '*'

class TiendaNubeWebHook(http.Controller):

    # https://tiendanube.github.io/api-documentation/resources/webhook#rules-for-deduplication
    # verificamos segun 3 segundos de diferencia en creacion del ultimo webhook igual
    def duplicity_check(self, data):
        webhook_received = request.env['webhook.tn.received'].sudo().search([
            ('id_event_tn','=',data['id']),('event','=',data['event']),('store_id','=',data['store_id'])
            ],limit=1, order='create_date desc')
        if webhook_received and (odoo.fields.Datetime.now() - webhook_received.create_date).seconds < 3:
            return True
        return False

    def _fetch_order_json_tn(self, company, order_id):
        """Pre-carga el JSON completo de una orden desde la API de TN."""
        try:
            url = "https://api.tiendanube.com/v1/%s/orders/%s" % (company.tiendanube_id, order_id)
            response = requests.get(url, headers=company.get_headers_tn())
            if response.status_code == 200:
                return response.json()
            _logger.warning('[Webhook TN] TN respondió %s al pre-cargar orden id=%s', response.status_code, order_id)
        except Exception as e:
            _logger.warning('[Webhook TN] Error pre-cargando JSON orden %s: %s', order_id, e)
        return None

    @http.route('/webhook_tn/<string:code_event>', auth='public', cors=CORS, csrf=False)
    def TiendaNubeWebHook(self, **kw):

        # Verificación de locking
        lock_name = 'webhook_processing'
        if request.env['ir.config_parameter'].sudo().get_param(lock_name) == 'En uso':
            return request.make_response(
                json.dumps({"mensaje": "Otra solicitud está en proceso"}),
                headers={'Content-Type': 'application/json'},
                status=429
            )

        request.env['ir.config_parameter'].sudo().set_param(lock_name, 'En uso')
        request.env.cr.commit()

        webhook_received_id = None
        data = {}

        try:
            data = json.loads(request.httprequest.get_data())

            # Verificacion de duplicidad
            if self.duplicity_check(data):
                _logger.info('[Webhook TN] Evento duplicado ignorado: %s id=%s', data.get('event'), data.get('id'))
                return request.make_response(
                    json.dumps({"mensaje": "Operación duplicada"}),
                    headers={'Content-Type': 'application/json'},
                    status=200
                )
            else:
                webhook_received = request.env['webhook.tn.received'].sudo().create({
                    'name': 'Evento: ' + data['event'] + ' - ID: ' + str(data['id']) + ' - Store ID:' + str(data['store_id']),
                    'id_event_tn': data['id'],
                    'event': data['event'],
                    'store_id': data['store_id'],
                })
                webhook_received_id = webhook_received.id
                request.env.cr.commit()

            if 'code_event' in kw:
                code_event = kw['code_event']
                webhook = request.env['webhook.tn'].sudo().search([
                    ('url','=',request.env['ir.config_parameter'].sudo().get_param('web.base.url') + '/webhook_tn/' + code_event)
                    ],limit=1)
                exitoso = False

                company_id = webhook.company_id if webhook.company_id else None
                if webhook:
                    # CATEGORIAS
                    if webhook.event == 'category/updated':
                        category = request.env['category.tn'].sudo().search([
                            ('tn_id','=',data['id'])
                            ],limit=1)
                        if category:
                            category.sudo().with_company(company_id).update_category_tn_odoo()
                        exitoso = True

                    elif webhook.event == 'category/created':
                        webhook.company_id.sudo().get_all_categories_tn()
                        exitoso = True

                    elif webhook.event == 'category/deleted':
                        category = request.env['category.tn'].sudo().search([
                            ('tn_id','=',data['id'])
                            ],limit=1)
                        if category:
                            category.sudo().unlink()
                        exitoso = True

                    # PRODUCTOS
                    elif webhook.event == 'product/deleted':
                        product = request.env['product.template'].sudo().search([
                            ('id_tn','=',data['id'])
                            ],limit=1)
                        if product:
                            product.sudo().write({
                                'active': False,
                                'name': product.name + ' #Producto eliminado desde Tienda Nube',
                                'barcode': False,
                                'default_code': False,
                            })
                        exitoso = True

                    elif webhook.event == 'product/created':
                        try:
                            product = request.env['product.template'].sudo().search([
                                ('id_tn','=',data['id'])
                                ],limit=1)
                            if not product:
                                product = request.env['product.template'].with_company(company_id).sudo().create({
                                    'id_tn': data['id'],
                                    'name': 'Nuevo Producto TN id: ' + str(data['id']),
                                })
                            product.sudo().with_company(company_id).create_update_product_from_tn()
                            exitoso = True
                        except Exception as e:
                            _logger.error('[Webhook TN] product/created id=%s: %s', data.get('id'), str(e), exc_info=True)
                            return request.make_response(
                                json.dumps({"mensaje": "Error al crear el producto"}),
                                headers={'Content-Type': 'application/json'},
                                status=500
                            )

                    elif webhook.event == 'product/updated':
                        product = request.env['product.template'].sudo().search([
                            ('id_tn','=',data['id'])
                            ],limit=1)
                        if product and (odoo.fields.Datetime.now() - product.write_date).seconds > 120:
                            try:
                                product.sudo().with_company(company_id).create_update_product_from_tn()
                            except Exception as e:
                                _logger.error('[Webhook TN] product/updated id=%s: %s', data.get('id'), str(e), exc_info=True)
                                return request.make_response(
                                    json.dumps({"mensaje": "Error al actualizar el producto"}),
                                    headers={'Content-Type': 'application/json'},
                                    status=500
                                )
                        exitoso = True

                    # ORDENES
                    # order/created: siempre crea en borrador, nunca confirma
                    elif webhook.event == 'order/created':
                        _logger.info('[Webhook TN] order/created id=%s', data['id'])
                        order = request.env['sale.order'].sudo().search([
                            ('id_tn','=',data['id'])
                            ],limit=1)
                        if not order:
                            order_json = self._fetch_order_json_tn(company_id, data['id'])
                            if order_json and webhook_received_id:
                                request.env['webhook.tn.received'].sudo().browse(webhook_received_id).write({
                                    'json_tn': json.dumps(order_json, ensure_ascii=False),
                                })
                                request.env.cr.commit()
                            if not order_json or not order_json.get('number'):
                                _logger.info('[Webhook TN] order/created id=%s ignorada: número de orden inválido (%s)', data['id'], order_json and order_json.get('number'))
                            else:
                                _logger.info('[Webhook TN] order/created id=%s — creando sale.order', data['id'])
                                order = request.env['sale.order'].with_company(company_id).sudo().create({
                                    'id_tn': data['id'],
                                    'partner_id': request.env.company.sudo().partner_id.id,
                                    'name': 'Orden TN id: ' + str(data['id']),
                                })
                                try:
                                    order.sudo().with_company(company_id).create_order_from_tn()
                                    _logger.info('[Webhook TN] order/created id=%s — orden %s procesada (state=%s)', data['id'], order.name, order.state)
                                except Exception as e:
                                    _logger.error('[Webhook TN] order/created id=%s — error en create_order_from_tn: %s', data['id'], str(e), exc_info=True)
                        else:
                            _logger.info('[Webhook TN] order/created id=%s — orden ya existe (%s), ignorando', data['id'], order.name)
                        exitoso = True

                    # order/paid: crea y valida; si existe en borrador, valida
                    elif webhook.event == 'order/paid':
                        _logger.info('[Webhook TN] order/paid id=%s', data['id'])
                        order = request.env['sale.order'].sudo().search([
                            ('id_tn','=',data['id'])
                            ],limit=1)
                        order_json = self._fetch_order_json_tn(company_id, data['id'])
                        if order_json and webhook_received_id:
                            request.env['webhook.tn.received'].sudo().browse(webhook_received_id).write({
                                'json_tn': json.dumps(order_json, ensure_ascii=False),
                            })
                            request.env.cr.commit()
                        _TN_TERMINAL_STATUSES = {'paid', 'cancelled', 'voided', 'refunded'}
                        if not order:
                            if not order_json or not order_json.get('number'):
                                _logger.info('[Webhook TN] order/paid id=%s ignorada: número de orden inválido (%s)', data['id'], order_json and order_json.get('number'))
                            else:
                                _logger.info('[Webhook TN] order/paid id=%s — orden nueva, creando', data['id'])
                                order = request.env['sale.order'].with_company(company_id).sudo().create({
                                    'id_tn': data['id'],
                                    'partner_id': request.env.company.sudo().partner_id.id,
                                    'name': 'Orden TN id: ' + str(data['id']),
                                })
                                try:
                                    order.sudo().with_company(company_id).create_order_from_tn()
                                    _logger.info('[Webhook TN] order/paid id=%s — orden %s procesada (state=%s, missing_products=%s)', data['id'], order.name, order.state, order.tn_has_missing_products)
                                except Exception as e:
                                    _logger.error('[Webhook TN] order/paid id=%s — error en create_order_from_tn: %s', data['id'], str(e), exc_info=True)
                                else:
                                    if order.state == 'draft' and not order.tn_has_missing_products and order_json.get('payment_status') not in _TN_TERMINAL_STATUSES:
                                        order.sudo()._tn_mark_for_payment_polling(order_json)
                        elif order.state == 'draft':
                            _logger.info('[Webhook TN] order/paid id=%s — orden %s en borrador, confirmando', data['id'], order.name)
                            try:
                                order.sudo()._tn_refresh_order_json(order_json)
                                order.sudo().with_company(company_id)._confirm_from_tn_paid()
                                _logger.info('[Webhook TN] order/paid id=%s — orden %s post-confirm (state=%s, missing_products=%s)', data['id'], order.name, order.state, order.tn_has_missing_products)
                                if not order.tn_has_missing_products:
                                    paid_status = (order_json.get('payment_status') or '') if order_json else ''
                                    if paid_status == 'paid':
                                        _logger.info('[Webhook TN] order/paid id=%s — aplicando config de pago', data['id'])
                                        order.sudo().with_company(company_id)._tn_apply_payment_config()
                                    elif paid_status not in _TN_TERMINAL_STATUSES and order_json:
                                        _logger.info('[Webhook TN] order/paid id=%s — marcando para polling (payment_status=%s)', data['id'], paid_status)
                                        order.sudo()._tn_mark_for_payment_polling(order_json)
                            except Exception as e:
                                _logger.error('[Webhook TN] order/paid id=%s — error procesando orden en borrador %s: %s', data['id'], order.name, str(e), exc_info=True)
                        else:
                            _logger.info('[Webhook TN] order/paid id=%s — orden %s ya confirmada (state=%s), sin cambios', data['id'], order.name, order.state)
                            order.sudo().message_post(body=_("Webhook order/paid recibido. La orden ya estaba confirmada — no se realizaron cambios."))
                        exitoso = True

                if exitoso:
                    return request.make_response(
                        json.dumps({"mensaje": "Operación exitosa"}),
                        headers={'Content-Type': 'application/json'},
                        status=200
                    )
                else:
                    return request.make_response(
                        json.dumps({"mensaje": "Operación no encontrada"}),
                        headers={'Content-Type': 'application/json'},
                        status=404
                    )
        except Exception as e:
            _logger.error(
                '[Webhook TN] Error no controlado procesando evento=%s id=%s: %s',
                data.get('event', '?'), data.get('id', '?'), str(e), exc_info=True,
            )
            return request.make_response(
                json.dumps({"mensaje": "Error al procesar la solicitud"}),
                headers={'Content-Type': 'application/json'},
                status=500
            )
        finally:
            try:
                # rollback limpia el estado de transacción abortada (error de BD) sin deshacer
                # los commits explícitos ya realizados arriba (webhook_received, json_tn, etc.)
                request.env.cr.rollback()
                request.env['ir.config_parameter'].sudo().set_param(lock_name, 'Disponible')
                request.env.cr.commit()
            except Exception as release_err:
                _logger.error('[Webhook TN] No se pudo liberar el lock webhook_processing: %s', release_err)
