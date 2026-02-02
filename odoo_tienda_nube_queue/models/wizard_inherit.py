# -*- coding: utf-8 -*-
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CreateAllProductsWizardQueue(models.TransientModel):
    _inherit = 'create.all.products.wizard'

    def create_all_products(self):
        """
        Override to use queue when enabled.
        If queue is disabled, falls back to original behavior.
        """
        company = self.env.company if self.env.company else self.env.user.company_id

        if company.tn_queue_enabled:
            Queue = self.env['tiendanube.sync.queue']
            count = Queue.queue_all_products_from_tn(company)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Productos Encolados'),
                    'message': _('%d productos han sido encolados para sincronización. '
                                 'Serán procesados automáticamente por el cron.') % count,
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'tiendanube.sync.queue',
                        'view_mode': 'list,form',
                        'domain': [('sync_type', '=', 'product'), ('state', '=', 'draft')],
                        'name': _('Cola de Productos'),
                    },
                },
            }

        return super().create_all_products()


class CreateAllCategoryWizardQueue(models.TransientModel):
    _inherit = 'create.all.category.wizard'

    def create_all_category(self):
        """
        Override to use queue when enabled.
        If queue is disabled, falls back to original behavior.
        """
        company = self.env.company if self.env.company else self.env.user.company_id

        if company.tn_queue_enabled:
            Queue = self.env['tiendanube.sync.queue']
            count = Queue.queue_all_categories_from_tn(company)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Categorías Encoladas'),
                    'message': _('%d categorías han sido encoladas para sincronización. '
                                 'Serán procesadas automáticamente por el cron.') % count,
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'tiendanube.sync.queue',
                        'view_mode': 'list,form',
                        'domain': [('sync_type', '=', 'category'), ('state', '=', 'draft')],
                        'name': _('Cola de Categorías'),
                    },
                },
            }

        return super().create_all_category()


class CreateAllOrdersWizardQueue(models.TransientModel):
    _inherit = 'create.all.orders.wizard'

    def create_all_orders(self):
        """
        Override to use queue when enabled.
        If queue is disabled, falls back to original behavior.
        """
        company = self.env.company if self.env.company else self.env.user.company_id

        if company.tn_queue_enabled:
            Queue = self.env['tiendanube.sync.queue']
            count = Queue.queue_all_orders_from_tn(company)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Órdenes Encoladas'),
                    'message': _('%d órdenes han sido encoladas para sincronización. '
                                 'Serán procesadas automáticamente por el cron.') % count,
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'tiendanube.sync.queue',
                        'view_mode': 'list,form',
                        'domain': [('sync_type', '=', 'order'), ('state', '=', 'draft')],
                        'name': _('Cola de Órdenes'),
                    },
                },
            }

        return super().create_all_orders()


class CreateAllCouponWizardQueue(models.TransientModel):
    _inherit = 'create.all.coupon.wizard'

    def create_all_coupon(self):
        """
        Override to use queue when enabled.
        If queue is disabled, falls back to original behavior.
        """
        company = self.env.company if self.env.company else self.env.user.company_id

        if company.tn_queue_enabled:
            Queue = self.env['tiendanube.sync.queue']
            count = Queue.queue_all_coupons_from_tn(company)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Cupones Encolados'),
                    'message': _('%d cupones han sido encolados para sincronización. '
                                 'Serán procesados automáticamente por el cron.') % count,
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'tiendanube.sync.queue',
                        'view_mode': 'list,form',
                        'domain': [('sync_type', '=', 'coupon'), ('state', '=', 'draft')],
                        'name': _('Cola de Cupones'),
                    },
                },
            }

        return super().create_all_coupon()
