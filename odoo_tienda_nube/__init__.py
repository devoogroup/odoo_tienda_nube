# -*- encoding: utf-8 -*-

from . import models
from . import wizards
from . import controllers


def _migrate_tn_confirmation_mode(env):
    """Preserva el comportamiento de auto-confirmación existente al introducir
    tn_confirmation_mode: las compañías con el viejo booleano tn_config_confirmation_sale
    en True pasan a 'always' en vez de quedar en el nuevo default 'never'."""
    env['res.company'].search([('tn_config_confirmation_sale', '=', True)]).write({
        'tn_confirmation_mode': 'always',
    })