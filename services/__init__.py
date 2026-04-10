import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.auth_service import (
    register_user,
    authenticate_user,
    create_user_access_token,
    get_user_by_id,
    get_user_by_email,
    get_user_by_username,
    update_user_profile,
    change_password,
    get_all_users,
    activate_user,
    deactivate_user,
    delete_user,
    get_user_count,
    get_active_user_count,
)
from services.transaction_service import (
    create_transaction,
    get_transactions,
    get_transaction_by_id,
    update_transaction,
    delete_transaction,
    get_transaction_summary,
    export_transactions_csv,
    get_recent_transactions,
    get_distinct_categories,
)
from services.category_service import (
    get_categories_for_user,
    get_system_categories,
    get_custom_categories,
    get_category_by_id,
    get_category_by_name_and_user,
    get_category_transaction_count,
    create_category,
    update_category,
    delete_category,
    create_system_category,
    update_system_category,
    delete_system_category,
    get_categories_with_transaction_counts,
    get_system_categories_with_transaction_counts,
    seed_default_categories,
)
from services.budget_service import (
    get_budgets_for_month,
    set_budget,
    check_overspend,
    bulk_save_budgets,
    delete_budget,
    get_budget_by_id,
    get_budget_summary,
)
from services.dashboard_service import (
    get_dashboard_summary,
    get_category_breakdown,
    get_admin_stats,
)