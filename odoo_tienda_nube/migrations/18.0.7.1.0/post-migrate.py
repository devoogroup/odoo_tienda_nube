# -*- coding: utf-8 -*-
"""Preserva el comportamiento de auto-confirmación al introducir tn_confirmation_mode:
las compañías con el viejo booleano tn_config_confirmation_sale en True pasan a
'always' en vez de quedar en el nuevo default 'never'."""


def migrate(cr, version):
    cr.execute("""
        UPDATE res_company
        SET tn_confirmation_mode = 'always'
        WHERE tn_config_confirmation_sale = true
    """)
