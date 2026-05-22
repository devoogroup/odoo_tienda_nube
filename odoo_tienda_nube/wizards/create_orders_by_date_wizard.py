from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time as dt_time, timezone as dt_timezone
from pytz import timezone as pytz_timezone
import requests
import logging

_logger = logging.getLogger(__name__)


class CreateOrdersByDateWizardLine(models.TransientModel):
    _name = 'create.orders.by.date.wizard.line'
    _description = 'Línea de preview de órdenes TN'
    _order = 'date_tn desc'

    wizard_id = fields.Many2one('create.orders.by.date.wizard', ondelete='cascade')
    order_id_tn = fields.Char(string='ID TN', readonly=True)
    number_tn = fields.Char(string='Número', readonly=True)
    date_tn = fields.Char(string='Fecha', readonly=True)
    contact_name = fields.Char(string='Comprador', readonly=True)
    total = fields.Char(string='Total', readonly=True)
    status_tn = fields.Char(string='Estado TN', readonly=True)
    payment_status_tn = fields.Char(string='Pago', readonly=True)
    in_odoo = fields.Boolean(string='Ya en Odoo', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Orden Odoo', readonly=True)
    import_result = fields.Selection([
        ('pending', 'Pendiente'),
        ('imported', 'Importada'),
        ('skipped', 'Omitida'),
        ('error', 'Error'),
    ], string='Resultado', default='pending', readonly=True)
    error_msg = fields.Char(string='Error', readonly=True)


class CreateOrdersByDateWizard(models.TransientModel):
    _name = 'create.orders.by.date.wizard'
    _description = 'Wizard para importar órdenes por rango de fechas'

    state = fields.Selection([
        ('draft', 'Configuración'),
        ('preview', 'Vista Previa'),
        ('done', 'Finalizado'),
    ], default='draft', string='Estado')

    date_from = fields.Date(string='Fecha desde', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Fecha hasta', required=True, default=fields.Date.today)
    include_cancelled = fields.Boolean(string='Incluir canceladas', default=False)

    line_ids = fields.One2many('create.orders.by.date.wizard.line', 'wizard_id', string='Órdenes')

    total_found = fields.Integer(string='Total encontradas', readonly=True)
    already_in_odoo = fields.Integer(string='Ya en Odoo', readonly=True)
    to_import = fields.Integer(string='A importar', readonly=True)
    imported_count = fields.Integer(string='Importadas', readonly=True)
    error_count = fields.Integer(string='Con error', readonly=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError('La fecha desde no puede ser mayor a la fecha hasta.')

    def action_check_preview(self):
        self.ensure_one()
        company = self.env.company or self.env.user.company_id
        headers = company.get_headers_tn()

        # La API de TN interpreta created_at_min/max como UTC.
        # Convertimos el inicio/fin del día en hora local de la tienda a UTC.
        tz_name = company.partner_id.tz or 'America/Argentina/Buenos_Aires'
        store_tz = pytz_timezone(tz_name)
        dt_from_utc = store_tz.localize(datetime.combine(self.date_from, dt_time(0, 0, 0))).astimezone(dt_timezone.utc)
        dt_to_utc = store_tz.localize(datetime.combine(self.date_to, dt_time(23, 59, 59))).astimezone(dt_timezone.utc)
        date_from_str = dt_from_utc.strftime('%Y-%m-%dT%H:%M:%S')
        date_to_str = dt_to_utc.strftime('%Y-%m-%dT%H:%M:%S')

        all_orders = []
        page = 1
        while True:
            url = (
                "https://api.tiendanube.com/v1/%s/orders"
                "?fields=id,number,status,total,contact_name,contact_email,created_at,payment_status"
                "&created_at_min=%s&created_at_max=%s&page=%s&per_page=200"
            ) % (company.tiendanube_id, date_from_str, date_to_str, page)
            if not self.include_cancelled:
                url += '&status=open,closed'
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if not data:
                    break
                all_orders.extend(data)
                if len(data) < 200:
                    break
                page += 1
            elif response.status_code == 404:
                break
            else:
                raise ValidationError('Error al consultar Tienda Nube: %s' % response.text)

        self.line_ids.unlink()

        lines_vals = []
        already_count = 0
        for order in all_orders:
            existing = self.env['sale.order'].search([('id_tn', '=', order['id'])], limit=1)
            in_odoo = bool(existing)
            if in_odoo:
                already_count += 1

            # Convertir created_at de TN a hora local de la tienda para mostrarlo correctamente
            created_at_raw = order.get('created_at', '')
            try:
                dt = datetime.strptime(created_at_raw, '%Y-%m-%dT%H:%M:%S%z')
                date_tn = dt.astimezone(store_tz).strftime('%Y-%m-%d %H:%M')
            except (ValueError, TypeError):
                date_tn = str(created_at_raw)[:16]

            lines_vals.append({
                'wizard_id': self.id,
                'order_id_tn': str(order.get('id', '')),
                'number_tn': str(order.get('number', '')),
                'date_tn': date_tn,
                'contact_name': order.get('contact_name') or order.get('contact_email') or '',
                'total': str(order.get('total', '')),
                'status_tn': order.get('status', ''),
                'payment_status_tn': order.get('payment_status', ''),
                'in_odoo': in_odoo,
                'sale_order_id': existing.id if existing else False,
                'import_result': 'skipped' if in_odoo else 'pending',
            })

        self.env['create.orders.by.date.wizard.line'].create(lines_vals)

        total = len(all_orders)
        self.write({
            'state': 'preview',
            'total_found': total,
            'already_in_odoo': already_count,
            'to_import': total - already_count,
        })
        return self._reopen()

    def action_import(self):
        self.ensure_one()
        imported = 0
        errors = 0

        # Capturar IDs como valores Python antes del loop para evitar
        # accesos ORM en estado de transacción abortada
        pending = [
            (line.id, line.order_id_tn)
            for line in self.line_ids.filtered(lambda l: l.import_result == 'pending')
        ]
        WizardLine = self.env['create.orders.by.date.wizard.line']
        public_partner_id = self.env.ref('base.public_partner').id

        for line_id, order_id_tn in pending:
            try:
                existing = self.env['sale.order'].search([('id_tn', '=', order_id_tn)], limit=1)
                if existing:
                    WizardLine.browse(line_id).write({
                        'import_result': 'skipped',
                        'sale_order_id': existing.id,
                        'in_odoo': True,
                    })
                else:
                    new_order = self.env['sale.order'].create({
                        'id_tn': order_id_tn,
                        'partner_id': public_partner_id,
                    })
                    new_order.with_context(tn_historical_import=True).create_order_from_tn()
                    WizardLine.browse(line_id).write({
                        'import_result': 'imported',
                        'sale_order_id': new_order.id,
                        'in_odoo': True,
                    })
                    imported += 1
                self.env.cr.commit()
            except Exception as e:
                error_msg = str(e)[:250]
                _logger.error('Error importando orden TN %s: %s', order_id_tn, error_msg)
                errors += 1
                self.env.cr.rollback()
                WizardLine.browse(line_id).write({
                    'import_result': 'error',
                    'error_msg': error_msg,
                })
                self.env.cr.commit()

        self.write({
            'state': 'done',
            'imported_count': imported,
            'error_count': errors,
        })
        return self._reopen()

    def action_reset(self):
        self.line_ids.unlink()
        self.write({
            'state': 'draft',
            'total_found': 0,
            'already_in_odoo': 0,
            'to_import': 0,
            'imported_count': 0,
            'error_count': 0,
        })
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
