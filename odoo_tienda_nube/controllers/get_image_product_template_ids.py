from odoo import http
import base64
from odoo.http import request # -*- coding: utf-8 -*-
import logging
import io
from PIL import Image
_logger = logging.getLogger(__name__)


def _detect_image_format(binary_data):
    try:
        fmt = Image.open(io.BytesIO(binary_data)).format
        return fmt.lower() if fmt else 'png'
    except Exception:
        return 'png'


class PublicController(http.Controller):

    @http.route('/ati_tn_product_template_ids/<int:id>', type='http', auth='public')
    def serve_image(self, id, **kwargs):
        record = request.env['product.product'].sudo().browse(id)
        binary_data = base64.b64decode(record.image_1920)
        image_format = _detect_image_format(binary_data)
        headers = [('Content-Type', f'image/{image_format}')]
        return request.make_response(binary_data, headers)

    @http.route('/ati_tn_product_template_galery_ids/<int:id>', type='http', auth='public')
    def serve_image_galery(self, id, **kwargs):
        record = request.env['product.image.tn'].sudo().browse(id)
        binary_data = base64.b64decode(record.image_1920)
        image_format = _detect_image_format(binary_data)
        headers = [('Content-Type', f'image/{image_format}')]
        return request.make_response(binary_data, headers)