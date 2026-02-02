# -*- coding: utf-8 -*-
import base64
import json
import logging
import time
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TiendanubeSyncQueue(models.Model):
    _name = 'tiendanube.sync.queue'
    _description = 'Cola de Sincronización Tienda Nube'
    _order = 'priority asc, create_date asc'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )
    data_json = fields.Text(
        string='Datos JSON',
        help="JSON crudo recibido de Tienda Nube"
    )
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('processing', 'Procesando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft', index=True)
    sync_type = fields.Selection([
        ('product', 'Producto'),
        ('category', 'Categoría'),
        ('order', 'Orden'),
        ('coupon', 'Cupón'),
    ], string='Tipo', required=True, index=True)
    direction = fields.Selection([
        ('tn_to_odoo', 'TN → Odoo'),
        ('odoo_to_tn', 'Odoo → TN'),
    ], string='Dirección', default='tn_to_odoo')
    tiendanube_id = fields.Char(
        string='ID Tienda Nube',
        index=True,
        help="ID del recurso en Tienda Nube"
    )
    odoo_model = fields.Char(
        string='Modelo Odoo',
        help="Nombre técnico del modelo destino en Odoo"
    )
    odoo_id = fields.Integer(
        string='ID Odoo',
        help="ID del registro en Odoo"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    priority = fields.Selection([
        ('1', 'Alta'),
        ('2', 'Normal'),
        ('3', 'Baja'),
    ], string='Prioridad', default='2', index=True)
    retry_count = fields.Integer(
        string='Intentos',
        default=0
    )
    max_retries = fields.Integer(
        string='Máx. Reintentos',
        related='company_id.tn_queue_max_retries',
        store=True
    )
    error_message = fields.Text(
        string='Mensaje de Error'
    )
    processed_at = fields.Datetime(
        string='Procesado'
    )
    processing_time = fields.Float(
        string='Tiempo (seg)',
        digits=(10, 3),
        help="Tiempo de procesamiento en segundos"
    )
    created_at = fields.Datetime(
        string='Creado',
        default=fields.Datetime.now
    )
    webhook_event = fields.Char(
        string='Evento Webhook',
        help="Evento que generó este registro (ej: product/created)"
    )

    @api.depends('sync_type', 'tiendanube_id', 'direction')
    def _compute_name(self):
        type_labels = dict(self._fields['sync_type'].selection)
        direction_labels = {
            'tn_to_odoo': '→',
            'odoo_to_tn': '←',
        }
        for record in self:
            type_label = type_labels.get(record.sync_type, record.sync_type)
            direction = direction_labels.get(record.direction, '')
            record.name = f"[{type_label}] {record.tiendanube_id} ({direction})"

    # -------------------------------------------------------------------------
    # Creation Methods
    # -------------------------------------------------------------------------

    @api.model
    def create_from_webhook(self, webhook_data, company, event):
        """
        Creates a queue record from webhook data.
        Called by the webhook controller when queue is enabled.
        """
        sync_type = self._get_sync_type_from_event(event)
        if not sync_type:
            _logger.warning("Unknown event type: %s", event)
            return False

        priority = self._get_priority_from_event(event)

        return self.create({
            'data_json': json.dumps(webhook_data),
            'sync_type': sync_type,
            'tiendanube_id': str(webhook_data.get('id', '')),
            'company_id': company.id,
            'priority': priority,
            'webhook_event': event,
            'direction': 'tn_to_odoo',
        })

    @api.model
    def create_from_fetcher(self, data, sync_type, company):
        """
        Creates a queue record from fetcher data.
        Avoids duplicates by checking existing draft records.
        """
        tiendanube_id = str(data.get('id', ''))

        # Check for existing draft record with same type and TN ID
        existing = self.search([
            ('tiendanube_id', '=', tiendanube_id),
            ('sync_type', '=', sync_type),
            ('company_id', '=', company.id),
            ('state', '=', 'draft'),
        ], limit=1)

        if existing:
            # Update existing record with fresh data
            existing.write({
                'data_json': json.dumps(data),
                'created_at': fields.Datetime.now(),
            })
            return existing

        return self.create({
            'data_json': json.dumps(data),
            'sync_type': sync_type,
            'tiendanube_id': tiendanube_id,
            'company_id': company.id,
            'priority': '3',  # Fetcher items are low priority
            'direction': 'tn_to_odoo',
        })

    def _get_sync_type_from_event(self, event):
        """Maps webhook event to sync_type."""
        if not event:
            return False
        event_type = event.split('/')[0] if '/' in event else event
        mapping = {
            'product': 'product',
            'category': 'category',
            'order': 'order',
            'coupon': 'coupon',
        }
        return mapping.get(event_type, False)

    def _get_priority_from_event(self, event):
        """Returns priority based on event type."""
        high_priority = ['order/created', 'order/paid']
        normal_priority = ['product/created', 'category/created']
        # Everything else is low priority

        if event in high_priority:
            return '1'
        elif event in normal_priority:
            return '2'
        return '3'

    # -------------------------------------------------------------------------
    # Cron Methods
    # -------------------------------------------------------------------------

    @api.model
    def _cron_fetch_from_tn(self):
        """
        Cron A (Fetcher): Fetches updated data from Tienda Nube.
        Uses updated_at_min to get only recent changes.
        Runs every 5 minutes.
        """
        companies = self.env['res.company'].search([
            ('tiendanube_access_token', '!=', False),
            ('tn_queue_enabled', '=', True),
        ])

        for company in companies:
            try:
                self._fetch_products_from_tn(company)
                self._fetch_categories_from_tn(company)
                # Update last fetch timestamp
                company.write({'tn_last_fetch_datetime': fields.Datetime.now()})
            except Exception as e:
                _logger.error("Error fetching from TN for company %s: %s", company.name, str(e))

    def _fetch_products_from_tn(self, company):
        """Fetches products from Tienda Nube API."""
        headers = company.get_headers_tn()
        base_url = f"https://api.tiendanube.com/v1/{company.tiendanube_id}/products"

        params = {'per_page': 50}
        if company.tn_last_fetch_datetime:
            # Format datetime for TN API
            updated_at_min = company.tn_last_fetch_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            params['updated_at_min'] = updated_at_min

        page = 1
        while True:
            params['page'] = page
            try:
                response = requests.get(base_url, headers=headers, params=params, timeout=30)
                if response.status_code == 404:
                    break
                if response.status_code != 200:
                    _logger.error("Error fetching products: %s", response.text)
                    break

                products = response.json()
                if not products:
                    break

                for product in products:
                    self.create_from_fetcher(product, 'product', company)

                page += 1
            except requests.exceptions.RequestException as e:
                _logger.error("Request error fetching products: %s", str(e))
                break

    def _fetch_categories_from_tn(self, company):
        """Fetches categories from Tienda Nube API."""
        headers = company.get_headers_tn()
        url = f"https://api.tiendanube.com/v1/{company.tiendanube_id}/categories"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                _logger.error("Error fetching categories: %s", response.text)
                return

            categories = response.json()
            for category in categories:
                self.create_from_fetcher(category, 'category', company)
        except requests.exceptions.RequestException as e:
            _logger.error("Request error fetching categories: %s", str(e))

    @api.model
    def _cron_process_queue(self):
        """
        Cron B (Worker): Processes queue records in batches.
        Runs every 1 minute.
        """
        companies = self.env['res.company'].search([
            ('tiendanube_access_token', '!=', False),
            ('tn_queue_enabled', '=', True),
        ])

        for company in companies:
            batch_size = company.tn_queue_batch_size or 50

            # Get pending records ordered by priority and creation date
            records = self.search([
                ('company_id', '=', company.id),
                ('state', '=', 'draft'),
            ], limit=batch_size, order='priority asc, create_date asc')

            for record in records:
                record._process_single_record()

    @api.model
    def _cron_cleanup_queue(self):
        """
        Cron C (Cleaner): Removes old processed records.
        Runs weekly.
        """
        companies = self.env['res.company'].search([
            ('tiendanube_access_token', '!=', False),
            ('tn_queue_enabled', '=', True),
        ])

        for company in companies:
            retention_days = company.tn_queue_retention_days or 15
            cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)

            old_records = self.search([
                ('company_id', '=', company.id),
                ('state', '=', 'done'),
                ('processed_at', '<', cutoff_date),
            ])

            if old_records:
                count = len(old_records)
                old_records.unlink()
                _logger.info("Cleaned up %d old queue records for company %s", count, company.name)

    # -------------------------------------------------------------------------
    # Wizard Queue Methods (Mass Enqueue)
    # -------------------------------------------------------------------------

    @api.model
    def queue_all_products_from_tn(self, company):
        """
        Queues all products from Tienda Nube for processing.
        Called by wizard when queue is enabled.
        Returns the number of products queued.
        """
        headers = company.get_headers_tn()
        queued_count = 0

        # First queue all categories to ensure they exist
        self.queue_all_categories_from_tn(company)

        # Fetch all products with pagination
        for page in range(1, 1000):
            url = f"https://api.tiendanube.com/v1/{company.tiendanube_id}/products?page={page}&per_page=50"
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 404:
                    break
                if response.status_code != 200:
                    raise ValidationError(f'Error al obtener productos de Tienda Nube: {response.text}')

                products = response.json()
                if not products:
                    break

                for product in products:
                    self.create_from_fetcher(product, 'product', company)
                    queued_count += 1

            except requests.exceptions.RequestException as e:
                raise ValidationError(f'Error de conexión con Tienda Nube: {str(e)}')

        _logger.info("Queued %d products from TN for company %s", queued_count, company.name)
        return queued_count

    @api.model
    def queue_all_categories_from_tn(self, company):
        """
        Queues all categories from Tienda Nube for processing.
        Called by wizard when queue is enabled.
        Returns the number of categories queued.
        """
        headers = company.get_headers_tn()
        url = f"https://api.tiendanube.com/v1/{company.tiendanube_id}/categories"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                raise ValidationError(f'Error al obtener categorías de Tienda Nube: {response.text}')

            categories = response.json()
            queued_count = 0

            for category in categories:
                self.create_from_fetcher(category, 'category', company)
                queued_count += 1

            _logger.info("Queued %d categories from TN for company %s", queued_count, company.name)
            return queued_count

        except requests.exceptions.RequestException as e:
            raise ValidationError(f'Error de conexión con Tienda Nube: {str(e)}')

    @api.model
    def queue_all_orders_from_tn(self, company):
        """
        Queues all orders from Tienda Nube for processing.
        Called by wizard when queue is enabled.
        Returns the number of orders queued.
        """
        headers = company.get_headers_tn()
        url = f"https://api.tiendanube.com/v1/{company.tiendanube_id}/orders?fields=id"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                raise ValidationError(f'Error al obtener órdenes de Tienda Nube: {response.text}')

            orders = response.json()
            queued_count = 0

            for order in orders:
                self.create_from_fetcher(order, 'order', company)
                queued_count += 1

            _logger.info("Queued %d orders from TN for company %s", queued_count, company.name)
            return queued_count

        except requests.exceptions.RequestException as e:
            raise ValidationError(f'Error de conexión con Tienda Nube: {str(e)}')

    @api.model
    def queue_all_coupons_from_tn(self, company):
        """
        Queues all coupons from Tienda Nube for processing.
        Called by wizard when queue is enabled.
        Returns the number of coupons queued.
        """
        headers = company.get_headers_tn()
        url = f"https://api.tiendanube.com/v1/{company.tiendanube_id}/coupons"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                raise ValidationError(f'Error al obtener cupones de Tienda Nube: {response.text}')

            coupons = response.json()
            queued_count = 0

            for coupon in coupons:
                self.create_from_fetcher(coupon, 'coupon', company)
                queued_count += 1

            _logger.info("Queued %d coupons from TN for company %s", queued_count, company.name)
            return queued_count

        except requests.exceptions.RequestException as e:
            raise ValidationError(f'Error de conexión con Tienda Nube: {str(e)}')

    # -------------------------------------------------------------------------
    # Processing Methods
    # -------------------------------------------------------------------------

    def _process_single_record(self):
        """
        Processes a single queue record with savepoint for transaction isolation.
        """
        self.ensure_one()
        start_time = time.time()

        # Mark as processing
        self.write({'state': 'processing'})
        self.env.cr.flush()

        try:
            with self.env.cr.savepoint():
                data = json.loads(self.data_json) if self.data_json else {}

                if self.sync_type == 'product':
                    self._process_product(data)
                elif self.sync_type == 'category':
                    self._process_category(data)
                elif self.sync_type == 'order':
                    self._process_order(data)
                elif self.sync_type == 'coupon':
                    self._process_coupon(data)

                # Mark as done
                processing_time = time.time() - start_time
                self.write({
                    'state': 'done',
                    'processed_at': fields.Datetime.now(),
                    'processing_time': processing_time,
                    'error_message': False,
                })

        except Exception as e:
            processing_time = time.time() - start_time
            self.retry_count += 1

            if self.retry_count >= (self.max_retries or 3):
                self.write({
                    'state': 'error',
                    'error_message': str(e),
                    'processed_at': fields.Datetime.now(),
                    'processing_time': processing_time,
                })
                _logger.error("Queue record %s failed after %d retries: %s",
                              self.id, self.retry_count, str(e))
            else:
                self.write({
                    'state': 'draft',
                    'error_message': f"Intento {self.retry_count}: {str(e)}",
                })
                _logger.warning("Queue record %s failed (attempt %d): %s",
                                self.id, self.retry_count, str(e))

    def _process_product(self, data):
        """Process a product sync record with full data from JSON."""
        self.ensure_one()
        company = self.company_id
        event = self.webhook_event or ''

        tiendanube_id = data.get('id')
        if not tiendanube_id:
            raise ValueError(_("No product ID in data"))

        Product = self.env['product.template'].sudo()

        if 'deleted' in event:
            # Handle product deletion
            product = Product.search([('id_tn', '=', tiendanube_id)], limit=1)
            if product:
                product.write({
                    'active': False,
                    'name': product.name + ' #Producto eliminado desde Tienda Nube',
                    'barcode': False,
                    'default_code': False,
                })
                self.odoo_model = 'product.template'
                self.odoo_id = product.id
            return

        # Check if we have full product data or just an ID
        has_full_data = 'name' in data and 'variants' in data

        if has_full_data:
            # Process product from stored JSON data (from wizard/fetcher)
            product = self._process_product_from_data(data, company)
        else:
            # Minimal data (from webhook) - fetch and process from TN API
            product = Product.search([('id_tn', '=', tiendanube_id)], limit=1)
            if not product:
                product = Product.with_company(company).create({
                    'id_tn': tiendanube_id,
                    'name': f'Nuevo Producto TN id: {tiendanube_id}',
                })
            product.with_company(company).create_update_product_from_tn()

        self.odoo_model = 'product.template'
        self.odoo_id = product.id

    def _process_product_from_data(self, product_data, company):
        """
        Creates/updates product template from full JSON data.
        Similar to create_products_in_odoo() but for a single product.
        """
        Product = self.env['product.template'].sudo()
        ProductProduct = self.env['product.product'].sudo()
        Category = self.env['category.tn'].sudo()
        Attribute = self.env['product.attribute'].sudo()
        AttributeValue = self.env['product.attribute.value'].sudo()

        tiendanube_id = product_data['id']

        # Get category IDs
        categoria_tn_ids = []
        for category in product_data.get('categories', []):
            category_odoo = Category.search([('tn_id', '=', category['id'])], limit=1)
            if category_odoo:
                categoria_tn_ids.append(category_odoo.id)

        # Get first image
        image_template_base64 = False
        if product_data.get('images'):
            url_imagen = product_data['images'][0].get('src')
            if url_imagen:
                try:
                    response = requests.get(url_imagen, timeout=30)
                    if response.status_code == 200:
                        image_template_base64 = base64.b64encode(response.content)
                except Exception as e:
                    _logger.warning("Could not fetch product image: %s", str(e))

        # Find or create product template
        product_template = Product.search([('id_tn', '=', tiendanube_id)], limit=1)

        product_name = product_data.get('name', {})
        if isinstance(product_name, dict):
            product_name = product_name.get('es', product_name.get('en', f'Producto TN {tiendanube_id}'))

        description = product_data.get('description', {})
        if isinstance(description, dict):
            description = description.get('es', description.get('en', ''))

        product_vals = {
            'id_tn': tiendanube_id,
            'name': product_name,
            'type': 'consu' if product_data.get('requires_shipping') else 'service',
            'is_storable': True if product_data.get('requires_shipping') else False,
            'envio_gratis_tn': product_data.get('free_shipping', False),
            'mostrar_en_tienda_tn': product_data.get('published', False),
            'categoria_tn_ids': [(6, 0, categoria_tn_ids)],
            'description_sale': description,
        }

        if image_template_base64:
            product_vals['image_1920'] = image_template_base64

        if not product_template:
            try:
                product_template = Product.with_company(company).create(product_vals)
            except Exception as e:
                _logger.error('Error creating product.template for TN ID %s: %s', tiendanube_id, str(e))
                raise
        else:
            product_template.write(product_vals)

        # Handle attributes and variants
        attributes = product_data.get('attributes', [])
        variants = product_data.get('variants', [])

        if attributes:
            index = 0
            for attribute in attributes:
                attr_name = attribute.get('es') if isinstance(attribute, dict) else attribute
                if not attr_name:
                    index += 1
                    continue

                # Find or create attribute
                attribute_odoo = Attribute.search([('name', '=', attr_name)], limit=1)
                if not attribute_odoo:
                    attribute_odoo = Attribute.create({
                        'name': attr_name,
                        'create_variant': 'always'
                    })

                # Collect unique values for this attribute
                value_ids = []
                for variant in variants:
                    if variant.get('values') and len(variant['values']) > index:
                        value_data = variant['values'][index]
                        value_name = value_data.get('es') if isinstance(value_data, dict) else value_data
                        if value_name:
                            value_odoo = AttributeValue.search([
                                ('name', '=', value_name),
                                ('attribute_id', '=', attribute_odoo.id)
                            ], limit=1)
                            if not value_odoo:
                                value_odoo = AttributeValue.create({
                                    'name': value_name,
                                    'attribute_id': attribute_odoo.id,
                                })
                            if value_odoo.id not in value_ids:
                                value_ids.append(value_odoo.id)

                index += 1

                # Add attribute line to product template if not exists
                existing_line = product_template.attribute_line_ids.filtered(
                    lambda x: x.attribute_id.id == attribute_odoo.id
                )
                if not existing_line:
                    product_template.write({
                        'attribute_line_ids': [(0, 0, {
                            'attribute_id': attribute_odoo.id,
                            'value_ids': [(6, 0, value_ids)],
                        })]
                    })
                else:
                    for value_id in value_ids:
                        if not existing_line.value_ids.filtered(lambda x: x.id == value_id):
                            existing_line.write({'value_ids': [(4, value_id)]})

        # Update variants
        for variant in variants:
            # Build attribute list to find the right product.product
            atributos = []
            index = 0
            for value in variant.get('values', []):
                attr_name = attributes[index] if index < len(attributes) else None
                if attr_name:
                    attr_name = attr_name.get('es') if isinstance(attr_name, dict) else attr_name
                value_name = value.get('es') if isinstance(value, dict) else value
                atributos.append({
                    'atributo': attr_name,
                    'valor': value_name,
                })
                index += 1

            # Find matching product variant
            product_variant_odoo = False
            for product_variant in product_template.product_variant_ids:
                atributos_variant = []
                for value in product_variant.product_template_attribute_value_ids:
                    atributos_variant.append({
                        'atributo': value.attribute_id.name,
                        'valor': value.name,
                    })
                if atributos == atributos_variant:
                    product_variant_odoo = product_variant
                    break

            if not product_variant_odoo and len(product_template.product_variant_ids) == 1:
                # Single variant product
                product_variant_odoo = product_template.product_variant_ids[0]

            if product_variant_odoo:
                # Get variant image
                variant_image = False
                if variant.get('image_id') and product_data.get('images'):
                    for image in product_data['images']:
                        if image['id'] == variant['image_id']:
                            try:
                                response = requests.get(image['src'], timeout=30)
                                if response.status_code == 200:
                                    variant_image = base64.b64encode(response.content)
                            except Exception:
                                pass
                            break

                # Check barcode uniqueness
                barcode = variant.get('barcode')
                if barcode:
                    existing_barcode = ProductProduct.search([('barcode', '=', barcode)], limit=1)
                    if existing_barcode and existing_barcode.id != product_variant_odoo.id:
                        barcode = False

                variant_vals = {
                    'product_id_tn': variant.get('id'),
                    'list_price': float(variant['price']) if variant.get('price') else 0,
                    'precio_promocional_tn': float(variant['promotional_price']) if variant.get('promotional_price') else 0,
                    'alto_tn': float(variant.get('height', 0)),
                    'ancho_tn': float(variant.get('width', 0)),
                    'profundidad_tn': float(variant.get('depth', 0)),
                    'peso_tn': float(variant.get('weight', 0)),
                    'mpn_tn': variant.get('mpn'),
                    'rango_edad_tn': variant.get('age_group'),
                    'sexo_tn': variant.get('gender'),
                    'default_code': variant.get('sku'),
                }

                if barcode:
                    variant_vals['barcode'] = barcode
                if variant_image:
                    variant_vals['image_1920'] = variant_image

                product_variant_odoo.write(variant_vals)

        return product_template

    def _process_category(self, data):
        """Process a category sync record."""
        self.ensure_one()
        company = self.company_id
        event = self.webhook_event or ''

        tiendanube_id = data.get('id')
        if not tiendanube_id:
            raise ValueError(_("No category ID in data"))

        Category = self.env['category.tn'].sudo()

        if 'deleted' in event:
            # Handle category deletion
            category = Category.search([('tn_id', '=', tiendanube_id)], limit=1)
            if category:
                category.unlink()
            return

        # Check if we have full category data
        has_full_data = 'name' in data

        if has_full_data:
            # Process from stored data
            category = self._process_category_from_data(data, company)
        elif 'updated' in event:
            # Handle category update via API
            category = Category.search([('tn_id', '=', tiendanube_id)], limit=1)
            if category:
                category.with_company(company).update_category_tn_odoo()
        else:
            # Handle category create - fetch all categories to ensure hierarchy
            company.get_all_categories_tn()
            category = Category.search([('tn_id', '=', tiendanube_id)], limit=1)

        if category:
            self.odoo_model = 'category.tn'
            self.odoo_id = category.id

    def _process_category_from_data(self, category_data, company):
        """Creates/updates category from full JSON data."""
        Category = self.env['category.tn'].sudo()

        tiendanube_id = category_data['id']

        # Get category name
        cat_name = category_data.get('name', {})
        if isinstance(cat_name, dict):
            cat_name = cat_name.get('es', cat_name.get('en', f'Categoría TN {tiendanube_id}'))

        # Find parent category
        parent_id = False
        parent_tn_id = category_data.get('parent')
        if parent_tn_id and parent_tn_id != 0:
            parent_category = Category.search([('tn_id', '=', parent_tn_id)], limit=1)
            if parent_category:
                parent_id = parent_category.id

        # Find or create category
        category = Category.search([('tn_id', '=', tiendanube_id)], limit=1)

        category_vals = {
            'name': cat_name,
            'tn_id': tiendanube_id,
            'parent_id': parent_id,
            'company_id': company.id,
        }

        if not category:
            category = Category.create(category_vals)
        else:
            category.write(category_vals)

        return category

    def _process_order(self, data):
        """Process an order sync record."""
        self.ensure_one()
        company = self.company_id

        tiendanube_id = data.get('id')
        if not tiendanube_id:
            raise ValueError(_("No order ID in data"))

        Order = self.env['sale.order'].sudo()
        order = Order.search([('id_tn', '=', tiendanube_id)], limit=1)

        if not order:
            order = Order.with_company(company).create({
                'id_tn': tiendanube_id,
                'partner_id': company.partner_id.id,
                'name': f'Orden TN id: {tiendanube_id}',
            })
            order.with_company(company).create_order_from_tn()

        self.odoo_model = 'sale.order'
        self.odoo_id = order.id

    def _process_coupon(self, data):
        """Process a coupon sync record."""
        self.ensure_one()
        company = self.company_id

        tiendanube_id = data.get('id')
        if not tiendanube_id:
            raise ValueError(_("No coupon ID in data"))

        Coupon = self.env['coupon.tn'].sudo()
        coupon = Coupon.search([('id_tn', '=', tiendanube_id)], limit=1)

        coupon_vals = {
            'name': data.get('code', ''),
            'id_tn': tiendanube_id,
            'type_tn': data.get('type'),
            'value': data.get('value'),
            'valid': data.get('valid'),
            'max_use': data.get('max_uses'),
            'includes_shipping': data.get('includes_shipping'),
            'min_price': data.get('min_price'),
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'used': data.get('used'),
        }

        if coupon:
            coupon.write(coupon_vals)
        else:
            coupon = Coupon.create(coupon_vals)

        self.odoo_model = 'coupon.tn'
        self.odoo_id = coupon.id

    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------

    def action_reprocess(self):
        """Button action to retry processing failed records."""
        for record in self:
            if record.state == 'error':
                record.write({
                    'state': 'draft',
                    'retry_count': 0,
                    'error_message': False,
                })
        return True

    def action_mark_done(self):
        """Button action to manually mark as done."""
        for record in self:
            record.write({
                'state': 'done',
                'processed_at': fields.Datetime.now(),
            })
        return True

    def action_view_odoo_record(self):
        """Button action to view the related Odoo record."""
        self.ensure_one()
        if not self.odoo_model or not self.odoo_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'res_model': self.odoo_model,
            'res_id': self.odoo_id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def action_process_queue_now(self):
        """
        Action to manually trigger queue processing.
        Useful for testing and immediate processing.
        """
        self._cron_process_queue()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cola Procesada'),
                'message': _('Se ha ejecutado el procesamiento de la cola.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def get_queue_stats(self, company_id=None):
        """
        Returns queue statistics for dashboard/monitoring.
        """
        domain = []
        if company_id:
            domain.append(('company_id', '=', company_id))

        stats = {
            'draft': self.search_count(domain + [('state', '=', 'draft')]),
            'processing': self.search_count(domain + [('state', '=', 'processing')]),
            'done': self.search_count(domain + [('state', '=', 'done')]),
            'error': self.search_count(domain + [('state', '=', 'error')]),
        }
        stats['total'] = sum(stats.values())
        return stats
