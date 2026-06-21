import logging
import requests
import base64

from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class SaleOrderTiendaNubeInherit(models.Model):
    _inherit = "sale.order"

    id_tn = fields.Char('ID Tienda Nube', help="ID de Tienda Nube", copy=False)
    number_tn = fields.Char('Numero de orden', help="Numero de orden de Tienda Nube", copy=False)
    token_tn = fields.Char('Token Tienda Nube', help="Token de Tieanda Nube", copy=False)
    store_id_tn = fields.Char('Store ID Tienda Nube', help="Store ID de Tienda Nube", copy=False)
    contact_email_tn = fields.Char('Email de contacto', help="Email de Tienda Nube", copy=False)
    contact_name_tn = fields.Char('Nombre de contacto', help="Nombre de Tienda Nube", copy=False)
    contact_phone_tn = fields.Char('Telefono de contacto', help="Telefono de Tienda Nube", copy=False)
    contact_identification_tn = fields.Char('Identificacion de contacto', help="Identificacion de Tienda Nube", copy=False)
    shipping_min_days_tn = fields.Char('Minimo de dias de envio', help="Minimo de dias de envio de Tienda Nube", copy=False)
    shipping_max_days_tn = fields.Char('Maximo de dias de envio', help="Maximo de dias de envio de Tienda Nube", copy=False)
    billing_name_tn = fields.Char('Nombre de facturacion', help="Nombre de facturacion de Tienda Nube", copy=False)
    billing_phone_tn = fields.Char('Telefono de facturacion', help="Telefono de facturacion de Tienda Nube", copy=False)
    billing_address_tn = fields.Char('Direccion de facturacion', help="Direccion de facturacion de Tienda Nube", copy=False)
    billing_number_tn = fields.Char('Numero', help="Numero Direccion de facturacion de Tienda Nube", copy=False)
    billing_floor_tn = fields.Char('Piso', help="Piso Direccion de facturacion de Tienda Nube", copy=False)
    billing_locality_tn = fields.Char('Localidad', help="Localidad Direccion de facturacion de Tienda Nube", copy=False)
    billing_zipcode_tn = fields.Char('Codigo Postal', help="Codigo Postal Direccion de facturacion de Tienda Nube", copy=False)
    billing_city_tn = fields.Char('Ciudad', help="Ciudad Direccion de facturacion de Tienda Nube", copy=False)
    billing_province_tn = fields.Char('Provincia', help="Provincia Direccion de facturacion de Tienda Nube", copy=False)
    billing_country_tn = fields.Char('Pais', help="Pais Direccion de facturacion de Tienda Nube", copy=False)
    billing_customer_type_tn = fields.Char('Tipo de cliente', help="Tipo de cliente de Tienda Nube", copy=False)
    billing_business_name_tn = fields.Char('Razon Social', help="Razon Social de Tienda Nube", copy=False)
    billing_trade_name_tn = fields.Char('Nombre Comercial', help="Nombre Comercial de Tienda Nube", copy=False)
    billing_state_registration_tn = fields.Char('Inscripcion Estatal', help="Inscripcion Estatal de Tienda Nube", copy=False)
    billing_document_type_tn = fields.Char('Tipo de documento', help="Tipo de documento de Tienda Nube", copy=False)

    # Shipping
    shipping_min_days_tn = fields.Char('Minimo de dias de envio', help="Minimo de dias de envio de Tienda Nube", copy=False)
    shipping_max_days_tn = fields.Char('Maximo de dias de envio', help="Maximo de dias de envio de Tienda Nube", copy=False)
    shipping_cost_owner_tn = fields.Float('Costo de envio propietario', help="Costo de envio propietario de Tienda Nube", copy=False)
    shipping_cost_customer_tn = fields.Float('Costo de envio cliente', help="Costo de envio cliente de Tienda Nube", copy=False)
    shipping_tn = fields.Char('Envio', help="Envio de Tienda Nube", copy=False)
    shipping_option_tn = fields.Char('Opcion de envio', help="Opcion de envio de Tienda Nube", copy=False)
    shipping_option_code_tn = fields.Char('Codigo de opcion de envio', help="Codigo de opcion de envio de Tienda Nube", copy=False)
    shipping_option_reference_tn = fields.Char('Referencia de opcion de envio', help="Referencia de opcion de envio de Tienda Nube", copy=False)
    shipping_pickup_details_tn = fields.Char('Detalles de recoleccion', help="Detalles de recoleccion de Tienda Nube", copy=False)
    shipping_tracking_number_tn = fields.Char('Numero de seguimiento', help="Numero de seguimiento de Tienda Nube", copy=False)
    shipping_tracking_url_tn = fields.Char('URL de seguimiento', help="URL de seguimiento de Tienda Nube", copy=False)
    shipping_store_branch_name_tn = fields.Char('Nombre de sucursal', help="Nombre de sucursal de Tienda Nube", copy=False)
    shipping_store_branch_extra_tn = fields.Char('Extra de sucursal', help="Extra de sucursal de Tienda Nube", copy=False)
    shipping_pickup_type_tn = fields.Char('Tipo de recoleccion', help="Tipo de recoleccion de Tienda Nube", copy=False)

    coupon_tn_ids = fields.Many2many('coupon.tn', string='Cupones Tienda Nube', help="Cupones de Tienda Nube", readonly=True)
    promotions_applied_tn = fields.Text('Promociones aplicadas', help="Promociones aplicadas de Tienda Nube", copy=False)

    json_tn = fields.Text('JSON Tienda Nube', help="JSON de Tienda Nube", copy=False)
    tn_has_missing_products = fields.Boolean(
        string='Productos TN faltantes',
        default=False,
        copy=False,
        help="La orden tiene productos de Tienda Nube no sincronizados con Odoo. Se mantiene en borrador hasta resolver.",
    )

    # Metodo para crear la orden en Odoo desde TN GET /orders/{id}
    def create_order_from_tn(self):
        if self.state != 'draft':
            raise ValidationError(_("La orden de venta debe estar en estado Borrador para poder ser editada por Tienda Nube"))
        try:
            if self.env.context.get('company_id'):
                company = self.env['res.company'].browse(self.env.context.get('company_id'))
            else:
                # NOTE: Utilizamos la compañia que tiene seleccionada el usuario actual o en caso contrario la compañia predeterminada de ese usuario
                company = self.env.company if self.env.company else self.env.user.company_id
            headers = company.get_headers_tn()
            url = "https://api.tiendanube.com/v1/%s/orders/%s?aggregates=fulfillment_orders" % (company.tiendanube_id, self.id_tn)
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                order = response.json()

                # Limpiamos lineas de la orden en el caso de que se este actualizando a fuerza
                if self.state == 'draft':
                    for line in self.order_line:
                        line.unlink()


                # Datos de la orden
                #verificamos por potencial error de Tienda Nube que la fecha no sea nula por ejemplo "-0001-11-30T00:00:00+0000", de ser incorrecta tomamos la fecha del dia
                if order['created_at'] == "-0001-11-30T00:00:00+0000":
                    order['created_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%z')
                try:
                    created_at = datetime.strptime(order['created_at'], '%Y-%m-%dT%H:%M:%S%z')
                except ValueError:
                    created_at = datetime.strptime(order['created_at'], '%Y-%m-%dT%H:%M:%S')
                # Convertir a UTC: Odoo almacena datetimes en UTC internamente.
                # Sin la conversión, la fecha se desplaza según el offset de zona horaria.
                from datetime import timezone as dt_timezone
                if created_at.tzinfo is not None:
                    created_at_utc = created_at.astimezone(dt_timezone.utc).replace(tzinfo=None)
                else:
                    created_at_utc = created_at
                self.date_order = created_at_utc.strftime('%Y-%m-%d %H:%M:%S')
                self.name = 'Tienda Nube #' + str(order['number']) + ' - ID: ' + str(order['id'])
                self.json_tn = order
                self.id_tn = order['id']
                self.number_tn = order['number']
                self.token_tn = order['token']
                self.store_id_tn = order['store_id']
                self.contact_email_tn = order['contact_email']
                self.contact_name_tn = order['contact_name']
                self.contact_phone_tn = order['contact_phone']
                self.contact_identification_tn = order['contact_identification']
                self.shipping_min_days_tn = order['shipping_min_days']
                self.shipping_max_days_tn = order['shipping_max_days']
                self.billing_name_tn = order['billing_name']
                self.billing_phone_tn = order['billing_phone']
                self.billing_address_tn = order['billing_address']
                self.billing_number_tn = order['billing_number']
                self.billing_floor_tn = order['billing_floor']
                self.billing_locality_tn = order['billing_locality']
                self.billing_zipcode_tn = order['billing_zipcode']
                self.billing_city_tn = order['billing_city']
                self.billing_province_tn = order['billing_province']
                self.billing_country_tn = order['billing_country']
                self.billing_customer_type_tn = order['billing_customer_type'] if order['billing_customer_type'] != "None" else False
                self.billing_business_name_tn = order['billing_business_name'] if order['billing_business_name'] != "None" else False
                self.billing_trade_name_tn = order['billing_trade_name'] if order['billing_trade_name'] != "None" else False
                self.billing_state_registration_tn = order['billing_state_registration'] if order['billing_state_registration'] != "None" else False
                self.billing_document_type_tn = order['billing_document_type'] if order['billing_document_type'] != "None" else False
                self.shipping_cost_owner_tn = float(order['shipping_cost_owner']) if order['shipping_cost_owner'] else 0
                self.shipping_cost_customer_tn = float(order['shipping_cost_customer']) if order['shipping_cost_customer'] else 0
                self.shipping_tn = order['shipping']
                self.shipping_min_days_tn = order['shipping_min_days']
                self.shipping_max_days_tn = order['shipping_max_days']
                self.shipping_option_tn = order['shipping_option']
                self.shipping_option_code_tn = order['shipping_option_code']
                self.shipping_option_reference_tn = order['shipping_option_reference']
                self.shipping_pickup_details_tn = order['shipping_pickup_details']
                self.shipping_tracking_number_tn = order['shipping_tracking_number']
                self.shipping_tracking_url_tn = order['shipping_tracking_url']
                self.shipping_store_branch_name_tn = order['shipping_store_branch_name']
                self.shipping_store_branch_extra_tn = order['shipping_store_branch_extra']
                self.shipping_pickup_type_tn = order['shipping_pickup_type']

                # Buscamos el cliente (solo activos, excluyendo subcontactos)
                partner = self.env['res.partner']
                _partner_base_domain = [
                    ('active', '=', True),
                    ('type', 'in', ['contact', False]),
                ]
                if order['contact_identification'] != None:
                    partner = self.env['res.partner'].search(
                        _partner_base_domain + [('vat', '=', order['contact_identification'])], limit=1)
                elif order['contact_email'] != None:
                    partner = self.env['res.partner'].search(
                        _partner_base_domain + [('email', '=', order['contact_email'])], limit=1)
                if not partner:
                    # Dirección de facturación (se copia al partner principal solo en la primera creación)
                    street_parts = [order.get('billing_address') or '']
                    if order.get('billing_number'):
                        street_parts.append(order['billing_number'])
                    street = ' '.join(filter(None, street_parts)) or False
                    country = self.env['res.country'].search([('code', '=', order.get('billing_country'))], limit=1)
                    state = False
                    if order.get('billing_province') and country:
                        state = self.env['res.country.state'].search([
                            ('name', 'ilike', order['billing_province']),
                            ('country_id', '=', country.id),
                        ], limit=1)
                    # Tipo de documento
                    billing_document_type = order.get('billing_document_type') or (order.get('customer') or {}).get('document_type')
                    l10n_latam_id = False
                    if billing_document_type:
                        id_type = self.env['l10n_latam.identification.type'].search([('name', 'ilike', billing_document_type)], limit=1)
                        if id_type:
                            l10n_latam_id = id_type.id
                    elif order.get('billing_country') == 'AR':
                        identification = order.get('contact_identification') or (order.get('customer') or {}).get('identification') or ''
                        digits = ''.join(filter(str.isdigit, str(identification)))
                        if len(digits) in (7, 8):
                            doc_name = 'DNI'
                        elif len(digits) in (10, 11):
                            doc_name = 'CUIT'
                        else:
                            doc_name = None
                        if doc_name:
                            id_type = self.env['l10n_latam.identification.type'].search([('name', 'ilike', doc_name)], limit=1)
                            if id_type:
                                l10n_latam_id = id_type.id
                    _billing_street2_parts = filter(None, [
                        order.get('billing_floor') or '',
                        order.get('billing_locality') or '',
                    ])
                    partner_vals = {
                        'name': order['customer']['name'] if 'customer' in order else order['contact_name'],
                        'email': order['customer']['email'] if 'customer' in order else order['contact_email'],
                        'phone': order['customer']['phone'] if 'customer' in order else order['contact_phone'],
                        'vat': order['customer']['identification'] if 'customer' in order else order['contact_identification'],
                        'company_type': 'person',
                        'street': street,
                        'street2': ', '.join(_billing_street2_parts) or False,
                        'zip': order.get('billing_zipcode') or False,
                        'city': order.get('billing_city') or False,
                        'state_id': state.id if state else False,
                        'country_id': country.id if country else False,
                    }
                    if l10n_latam_id:
                        partner_vals['l10n_latam_identification_type_id'] = l10n_latam_id
                    partner = self.env['res.partner'].create(partner_vals)
                # Sub-contacto facturación: siempre creamos/buscamos un hijo type='invoice'
                invoice_partner = self._tn_get_or_create_invoice_partner(partner, order)
                self.partner_id = partner.id
                self.partner_invoice_id = invoice_partner.id
                # Default envío = facturación; se sobreescribe abajo si las direcciones difieren
                self.partner_shipping_id = invoice_partner.id
                # Sub-contacto entrega: si TN provee shipping_address con calle, creamos/buscamos el hijo
                _shipping_address = order.get('shipping_address') or {}
                if _shipping_address.get('address'):
                    _delivery_partner = self._tn_get_or_create_delivery_partner(partner, _shipping_address)
                    if _delivery_partner:
                        self.partner_shipping_id = _delivery_partner.id

                # Completamos lineas de la orden
                self.tn_has_missing_products = False  # reset por si es un reprocesamiento
                missing_lines = []
                for line in order['products']:
                    product = self.env['product.product'].search([('product_id_tn', '=', line['variant_id'])], limit=1)

                    if not product:
                        missing_lines.append("'%s' (TN id: %s)" % (line['name'], line['variant_id']))
                        continue
                    #Verificamos si tenemos que quitar impuestos
                    price_unit = float(line['price'])
                    if self.company_id.tn_type_tax == 'not_included':
                        value_tax = (((product.taxes_id.compute_all(price_unit)['total_included']) * 100) / (product.taxes_id.compute_all(price_unit)['total_excluded'])) / 100
                        price_unit = price_unit / value_tax
                    self.env['sale.order.line'].create({
                        'name': line['name'],
                        'order_id': self.id,
                        'product_id': product.id,
                        'product_uom_qty': float(line['quantity']),
                        'price_unit': price_unit,
                    })
                if missing_lines:
                    _logger.warning(
                        '[TN] Orden %s: productos no encontrados en Odoo: %s',
                        self.id_tn, ', '.join(missing_lines),
                    )
                    self.env['tn.log'].create_log(
                        'Productos no encontrados — %s' % self.name,
                        'Líneas omitidas por no estar sincronizadas con Odoo: %s' % ', '.join(missing_lines),
                        'sale.order',
                        self.id,
                        'error',
                    )
                    self.tn_has_missing_products = True

                # DESCUENTOS
                if len(order['coupon']) or len(order['promotional_discount']['promotions_applied']):
                    product_discount_tn = self.env.ref('odoo_tienda_nube.product_discount_tn')
                    if not product_discount_tn:
                        raise ValidationError(_("Producto de descuento no encontrado en Odoo"))
                    # Agregamos seccion de descuento en Sale Order
                    self.write(
                        {'order_line':[(0, 0, {
                            'display_type': 'line_section',
                            'name': 'Descuentos Aplicados',
                            })]
                        }
                    )

                    # Verificamos por cupones de descuento
                    for coupon in order['coupon']:
                        coupon_tn = self.env['coupon.tn'].search([('id_tn', '=', coupon['id'])], limit=1)
                        if not coupon_tn:
                            coupon_tn = self.env['coupon.tn'].create({
                                'id_tn': coupon['id'],
                                'name': coupon['code'],
                                'type_tn': coupon['type'],
                                'value': coupon['value'],
                                'valid': coupon['valid'],
                                'max_use': coupon['max_uses'],
                                'includes_shipping': coupon['includes_shipping'],
                                'min_price': coupon['min_price'],
                                'start_date': coupon['start_date'],
                                'end_date': coupon['end_date'],
                            })
                        self.coupon_tn_ids = [(4, coupon_tn.id)]
                        discount_coupon_amount = float(order['discount_coupon'])
                        if self.company_id.tn_type_tax == 'not_included':
                            value_tax = (((product_discount_tn.taxes_id.compute_all(discount_coupon_amount)['total_included']) * 100) / (product_discount_tn.taxes_id.compute_all(discount_coupon_amount)['total_excluded'])) / 100
                            if value_tax:
                                discount_coupon_amount = discount_coupon_amount / value_tax
                        self.env['sale.order.line'].create({
                            'name': 'Descuento por cupón (' + coupon['code'] + ')',
                            'order_id': self.id,
                            'product_id': product_discount_tn.id,
                            'product_uom_qty': -1,
                            'price_unit': discount_coupon_amount,
                        })
                    # Verificamos por promociones aplicadas
                    if 'promotions_applied' in order['promotional_discount']:
                        for promotions_applied in order['promotional_discount']['promotions_applied']:
                            if self.promotions_applied_tn:
                                self.promotions_applied_tn += "Tipo: " + promotions_applied['discount_script_type'] + " - Descuento: " + promotions_applied['total_discount_amount_short'] + "\n"
                            else:
                                self.promotions_applied_tn = "Tipo: " + promotions_applied['discount_script_type'] + " - Descuento: " + promotions_applied['total_discount_amount_short'] + "\n"
                            discount_promo_amount = float(promotions_applied['total_discount_amount'])
                            if self.company_id.tn_type_tax == 'not_included':
                                value_tax = (((product_discount_tn.taxes_id.compute_all(discount_promo_amount)['total_included']) * 100) / (product_discount_tn.taxes_id.compute_all(discount_promo_amount)['total_excluded'])) / 100
                                if value_tax:
                                    discount_promo_amount = discount_promo_amount / value_tax
                            self.env['sale.order.line'].create({
                                'name': 'Promoción %s' % (promotions_applied.get('discount_script_type') or ''),
                                'order_id': self.id,
                                'product_id': product_discount_tn.id,
                                'product_uom_qty': -1,
                                'price_unit': discount_promo_amount,
                            })

                # ENVIO
                product_shipping_tn = self.env.ref('odoo_tienda_nube.product_shipping_tn')
                if not product_shipping_tn:
                    raise ValidationError(_("Producto de envio no encontrado en Odoo"))

                #Verificamos si tenemos que quitar impuestos
                price_shipping = float(order['shipping_cost_customer']) if order['shipping_cost_customer'] else 0
                if self.company_id.tn_type_tax == 'not_included' and price_shipping > 0:
                    value_tax = (((product_shipping_tn.taxes_id.compute_all(price_shipping)['total_included']) * 100) / (product_shipping_tn.taxes_id.compute_all(price_shipping)['total_excluded'])) / 100
                    if value_tax:
                        price_shipping = price_shipping / value_tax

                self.env['sale.order.line'].create({
                    'name': 'Costo de Envío (%s)' % (order.get('shipping_option') or ''),
                    'order_id': self.id,
                    'product_id': product_shipping_tn.id,
                    'product_uom_qty': 1,
                    'price_unit': price_shipping,
                })

                #Verificamos si hay Almacen de salida
                if len(order['fulfillments']) > 0:
                    # Buscamos el Almacen de salida
                    warehouse_id = self.env['stock.warehouse'].search([('location_id_tn', '=', order['fulfillments'][0]['assigned_location']['location_id'])], limit=1)
                    if not warehouse_id:
                        raise ValidationError(_("Almacen de salida no encontrada en Odoo"))
                    self.warehouse_id = warehouse_id.id

                # Verificamos si debemos confirmar la orden
                if missing_lines:
                    self.message_post(body=_(
                        "⚠ Orden en borrador: los siguientes productos de Tienda Nube "
                        "no están sincronizados con Odoo y fueron omitidos. "
                        "Sincronizar los productos y reprocesar la orden manualmente.\n\n%s"
                    ) % '\n'.join('• ' + p for p in missing_lines))
                elif self._tn_should_auto_confirm(order):
                    self.action_confirm()
                    self.message_post(body=self._tn_confirm_message(order))
                else:
                    self.message_post(body=self._tn_pending_message(order))

                self.env['tn.log'].create_log('Orden de venta {0} creada'.format(self.name), 'Orden de Venta creada desde Tienda Nube', 'sale.order', self.id, 'success')
            else:
                self.env['tn.log'].create_log('No se pudo crear Orden de Venta', 'Error al obtener orden de Tienda Nube', 'sale.order', self.id, 'error', response.text)
        except Exception as e:
            # Creamos un log
            self.env['tn.log'].create_log('No se pudo crear Orden de Venta', str(e), 'sale.order', self.id, 'error')

    def _tn_should_auto_confirm(self, order):
        """Hook: devuelve True si la orden debe confirmarse automáticamente.
        Sobreescribible por módulos que agreguen nuevos modos de confirmación."""
        mode = self.company_id.tn_confirmation_mode
        payment_status = order.get('payment_status')
        return mode == 'always' or (mode == 'paid' and payment_status == 'paid')

    def _tn_confirm_message(self, order):
        """Hook: mensaje de chatter cuando la orden se confirma automáticamente."""
        return _("Orden confirmada automáticamente desde Tienda Nube (payment_status: %s).") % (order.get('payment_status') or '-')

    def _tn_pending_message(self, order):
        """Hook: mensaje de chatter cuando la orden queda en borrador."""
        return _("Orden recibida desde Tienda Nube. Estado de pago: %s. Pendiente de confirmación.") % (order.get('payment_status') or '-')

    def _tn_refresh_order_json(self, order_json):
        """Actualiza json_tn con datos frescos de TN. Extensible para sincronizar campos adicionales."""
        if order_json and order_json.get('number'):
            self.write({'json_tn': str(order_json)})

    def _tn_mark_for_payment_polling(self, order_json=None):
        """Hook: marcar orden para polling de estado de pago. Implementar en módulos de pago."""
        pass

    def _tn_handle_order_cancelled(self, order_json=None):
        """Hook: manejar webhook order/cancelled. Sobreescribir en módulos específicos."""
        pass

    def _confirm_from_tn_paid(self):
        """Procesa order/paid para una orden ya existente en borrador.
        Solo confirma según el modo configurado, sin re-procesar líneas ni datos."""
        self.ensure_one()
        if self.tn_has_missing_products:
            self.message_post(body=_(
                "⚠ Pago recibido desde Tienda Nube, pero la orden permanece en borrador: "
                "tiene productos no sincronizados con Odoo. "
                "Sincronizar los productos y reprocesar la orden manualmente."
            ))
            return
        mode = self.company_id.tn_confirmation_mode
        if mode in ('always', 'paid'):
            self.action_confirm()
            self.message_post(body=_("Orden confirmada: pago recibido desde Tienda Nube (webhook order/paid)."))
            self.env['tn.log'].create_log(
                'Orden %s confirmada por pago TN' % self.name,
                'Evento order/paid recibido — confirmación automática.',
                'sale.order', self.id, 'success',
            )
        else:
            self.message_post(body=_("Pago recibido desde Tienda Nube (webhook order/paid). La orden permanece en borrador según la configuración de confirmación."))
            self.env['tn.log'].create_log(
                'Pago TN recibido — orden %s en borrador' % self.name,
                'Evento order/paid recibido. Modo "Nunca confirmar": la orden no se confirma automáticamente.',
                'sale.order', self.id, 'success',
            )

    def _tn_get_or_create_invoice_partner(self, partner, order):
        """Busca o crea un partner hijo tipo 'invoice' con los datos de facturación de TN.

        Deduplicación por calle + ciudad (igual que delivery). Fallback a cualquier
        hijo invoice existente para no romper clientes migrados sin dirección en el hijo.
        """
        street_parts = [order.get('billing_address', "").strip() or '']
        if order.get('billing_number'):
            street_parts.append(order['billing_number'].strip())
        street = ' '.join(filter(None, street_parts)) or False
        billing_city = order.get('billing_city', "").strip() or ''
        billing_zip = order.get('billing_zipcode', "").strip() or False

        # Búsqueda precisa: misma calle + ciudad + código postal
        existing = self.env['res.partner'].search([
            ('parent_id', '=', partner.id),
            ('type', '=', 'invoice'),
            ('street', '=ilike', street),
            ('city', '=ilike', billing_city),
            ('zip', '=', billing_zip),
        ], limit=1)
        if existing:
            return existing

        country = self.env['res.country'].search([('code', '=', order.get('billing_country'))], limit=1)
        state = False
        if order.get('billing_province') and country:
            state = self.env['res.country.state'].search([
                ('name', 'ilike', order['billing_province']),
                ('country_id', '=', country.id),
            ], limit=1)

        name = order.get('billing_name', "").strip() or partner.name
        street2_parts = filter(None, [
            order.get('billing_floor') or '',
            order.get('billing_locality') or '',
        ])
        return self.env['res.partner'].create({
            'name': name,
            'type': 'invoice',
            'parent_id': partner.id,
            'phone': order.get('billing_phone', "").strip() or partner.phone or False,
            'street': street or False,
            'street2': ', '.join(street2_parts) or False,
            'zip': order.get('billing_zipcode', "").strip() or False,
            'city': order.get('billing_city', "").strip() or False,
            'state_id': state.id if state else False,
            'country_id': country.id if country else False,
        })

    def _tn_get_or_create_delivery_partner(self, partner, shipping_data):
        """Busca o crea un partner hijo tipo 'delivery' para la dirección de envío TN.

        Reutiliza un hijo existente si ya hay uno con la misma calle y ciudad.
        shipping_data: dict shipping_address del JSON de TN.
        """
        street_name = shipping_data.get('address', "").strip() or ''
        street_number = shipping_data.get('number', "").strip() or ''
        street = ('%s %s' % (street_name, street_number)).strip() or False
        city = shipping_data.get('city').strip() or ''

        if not street_name and not city:
            return False

        existing = self.env['res.partner'].search([
            ('parent_id', '=', partner.id),
            ('type', '=', 'delivery'),
            ('street', '=ilike', street),   # calle + número completo
            ('city', '=ilike', city),
        ], limit=1)
        if existing:
            return existing

        country_code = shipping_data.get('country') or ''
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        state = False
        if shipping_data.get('province') and country:
            state = self.env['res.country.state'].search([
                ('name', 'ilike', shipping_data['province']),
                ('country_id', '=', country.id),
            ], limit=1)

        name = shipping_data.get('name', "").strip() or partner.name
        street2_parts = filter(None, [
            shipping_data.get('floor') or '',
            shipping_data.get('locality') or '',
        ])
        street2 = ', '.join(street2_parts) or False

        return self.env['res.partner'].create({
            'name': name,
            'type': 'delivery',
            'parent_id': partner.id,
            'phone': shipping_data.get('phone') or partner.phone or False,
            'street': street or False,
            'street2': street2,
            'zip': shipping_data.get('zipcode') or False,
            'city': city or False,
            'state_id': state.id if state else False,
            'country_id': country.id if country else False,
        })
