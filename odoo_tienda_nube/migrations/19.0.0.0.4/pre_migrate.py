def migrate(cr, version):
    """Migra tn_config_confirmation_sale (boolean) → tn_confirmation_mode (selection)."""
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS tn_confirmation_mode VARCHAR;
    """)
    cr.execute("""
        UPDATE res_company
        SET tn_confirmation_mode = CASE
            WHEN tn_config_confirmation_sale = TRUE THEN 'always'
            ELSE 'never'
        END
        WHERE tn_confirmation_mode IS NULL;
    """)
