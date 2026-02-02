# -*- coding: utf-8 -*-
{
    "name": "Tienda Nube - Cola de Sincronización",
    "summary": """
        Sistema de cola optimizado para sincronización con Tienda Nube""",
    "description": """
        Módulo que implementa un sistema de cola de sincronización para Tienda Nube
        usando el patrón Staging Area con pipeline de 3 pasos:
        - Fetcher: Obtiene datos de Tienda Nube cada 5 minutos
        - Worker: Procesa la cola cada 1 minuto
        - Cleaner: Limpia registros antiguos semanalmente
    """,
    "category": "Sale",
    "version": "18.0.1.0.0",
    "website": "https://devoo.io",
    "author": "Iván Arriola | Valentin Romero - Devoo",
    "license": "LGPL-3",
    "depends": [
        "odoo_tienda_nube",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/multi_company_rules.xml",
        "data/cron_fetcher.xml",
        "data/cron_worker.xml",
        "data/cron_cleaner.xml",
        "views/sync_queue_views.xml",
        "views/res_company_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
