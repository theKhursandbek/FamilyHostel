"""
Backup & Restore system for FamilyHostel (Step 26).

Provides:
    - backup_db / restore_db management commands
    - Local & Azure Blob backup storage backends
    - Celery Beat scheduled tasks (daily / weekly)
    - Retention policy (7 daily, 4 weekly)
"""
