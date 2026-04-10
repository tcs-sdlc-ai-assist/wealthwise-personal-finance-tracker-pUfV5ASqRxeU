import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, and_, desc
from sqlalchemy.orm import Session

from database import get_db
from models.transaction import Transaction
from models.category import Category


def create_transaction(
    db: Session,
    user_id: str,
    amount: Decimal,
    type: str,
    category: str,
    description: Optional[str] = None,
    transaction_date: Optional[date] = None,
    account_id: Optional[str] = None,
    category_id: Optional[str] = None,
) -> Transaction:
    if transaction_date is None:
        transaction_date = date.today()

    if category_id is None:
        cat_result = db.execute(
            select(Category).where(
                and_(
                    Category.name == category,
                    (Category.user_id == user_id) | (Category.user_id.is_(None)),
                )
            )
        )
        cat = cat_result.scalars().first()
        if cat:
            category_id = cat.id

    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        type=type,
        category=category,
        description=description,
        transaction_date=transaction_date,
        account_id=account_id,
        category_id=category_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transactions(
    db: Session,
    user_id: str,
    type: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    account_id: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "transaction_date",
    sort_order: str = "desc",
) -> dict:
    query = select(Transaction).where(Transaction.user_id == user_id)

    query = _apply_filters(
        query,
        type=type,
        category=category,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        account_id=account_id,
    )

    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_count = db.execute(count_query).scalar() or 0

    sort_column = _get_sort_column(sort_by)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    transactions = list(result.scalars().all())

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return {
        "transactions": transactions,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


def get_transaction_by_id(
    db: Session,
    transaction_id: str,
    user_id: str,
) -> Optional[Transaction]:
    result = db.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
        )
    )
    return result.scalars().first()


def update_transaction(
    db: Session,
    transaction_id: str,
    user_id: str,
    amount: Optional[Decimal] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    transaction_date: Optional[date] = None,
    account_id: Optional[str] = None,
) -> Optional[Transaction]:
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    if transaction is None:
        return None

    if amount is not None:
        transaction.amount = amount
    if type is not None:
        transaction.type = type
    if category is not None:
        transaction.category = category
        cat_result = db.execute(
            select(Category).where(
                and_(
                    Category.name == category,
                    (Category.user_id == user_id) | (Category.user_id.is_(None)),
                )
            )
        )
        cat = cat_result.scalars().first()
        if cat:
            transaction.category_id = cat.id
    if description is not None:
        transaction.description = description
    if transaction_date is not None:
        transaction.transaction_date = transaction_date
    if account_id is not None:
        transaction.account_id = account_id

    transaction.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(
    db: Session,
    transaction_id: str,
    user_id: str,
) -> bool:
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    if transaction is None:
        return False

    db.delete(transaction)
    db.commit()
    return True


def get_transaction_summary(
    db: Session,
    user_id: str,
    type: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    account_id: Optional[str] = None,
) -> dict:
    base_query = select(Transaction).where(Transaction.user_id == user_id)
    base_query = _apply_filters(
        base_query,
        type=type,
        category=category,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        account_id=account_id,
    )

    subq = base_query.subquery()

    income_query = select(func.coalesce(func.sum(subq.c.amount), 0)).where(
        subq.c.type == "income"
    )
    total_income = db.execute(income_query).scalar() or Decimal("0.00")

    expense_query = select(func.coalesce(func.sum(subq.c.amount), 0)).where(
        subq.c.type == "expense"
    )
    total_expenses = db.execute(expense_query).scalar() or Decimal("0.00")

    count_query = select(func.count()).select_from(subq)
    total_count = db.execute(count_query).scalar() or 0

    total_income = Decimal(str(total_income))
    total_expenses = Decimal(str(total_expenses))
    net_balance = total_income - total_expenses

    return {
        "total_income": float(total_income),
        "total_expenses": float(total_expenses),
        "net_balance": float(net_balance),
        "total_count": total_count,
    }


def get_category_breakdown(
    db: Session,
    user_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    transaction_type: str = "expense",
) -> list:
    conditions = [
        Transaction.user_id == user_id,
        Transaction.type == transaction_type,
    ]
    if date_from is not None:
        conditions.append(Transaction.transaction_date >= date_from)
    if date_to is not None:
        conditions.append(Transaction.transaction_date <= date_to)

    query = (
        select(
            Transaction.category,
            func.sum(Transaction.amount).label("total_amount"),
            func.count(Transaction.id).label("count"),
        )
        .where(and_(*conditions))
        .group_by(Transaction.category)
        .order_by(desc("total_amount"))
    )

    result = db.execute(query)
    rows = result.all()

    grand_total = sum(float(row.total_amount) for row in rows) if rows else 0.0

    breakdown = []
    for row in rows:
        amount = float(row.total_amount)
        percentage = (amount / grand_total * 100) if grand_total > 0 else 0.0

        cat_result = db.execute(
            select(Category).where(
                and_(
                    Category.name == row.category,
                    (Category.user_id == user_id) | (Category.user_id.is_(None)),
                )
            )
        )
        cat = cat_result.scalars().first()
        color = cat.color if cat and cat.color else None

        breakdown.append({
            "name": row.category,
            "amount": amount,
            "count": row.count,
            "percentage": round(percentage, 1),
            "color": color,
        })

    return breakdown


def export_transactions_csv(
    db: Session,
    user_id: str,
    type: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    account_id: Optional[str] = None,
) -> str:
    query = select(Transaction).where(Transaction.user_id == user_id)
    query = _apply_filters(
        query,
        type=type,
        category=category,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        account_id=account_id,
    )
    query = query.order_by(Transaction.transaction_date.desc())

    result = db.execute(query)
    transactions = list(result.scalars().all())

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date",
        "Type",
        "Category",
        "Amount",
        "Description",
        "Account ID",
        "Transaction ID",
        "Created At",
    ])

    for txn in transactions:
        writer.writerow([
            str(txn.transaction_date) if txn.transaction_date else "",
            txn.type or "",
            txn.category or "",
            str(txn.amount) if txn.amount is not None else "0.00",
            txn.description or "",
            txn.account_id or "",
            txn.id or "",
            str(txn.created_at) if txn.created_at else "",
        ])

    csv_content = output.getvalue()
    output.close()
    return csv_content


def get_recent_transactions(
    db: Session,
    user_id: str,
    limit: int = 10,
) -> list:
    query = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(limit)
    )
    result = db.execute(query)
    return list(result.scalars().all())


def get_distinct_categories(
    db: Session,
    user_id: str,
) -> list:
    query = (
        select(Transaction.category)
        .where(Transaction.user_id == user_id)
        .distinct()
        .order_by(Transaction.category.asc())
    )
    result = db.execute(query)
    return [row[0] for row in result.all() if row[0]]


def _apply_filters(
    query,
    type: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    account_id: Optional[str] = None,
):
    if type is not None and type != "":
        query = query.where(Transaction.type == type)
    if category is not None and category != "":
        query = query.where(Transaction.category == category)
    if date_from is not None:
        query = query.where(Transaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.where(Transaction.transaction_date <= date_to)
    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)
    if account_id is not None and account_id != "":
        query = query.where(Transaction.account_id == account_id)
    return query


def _get_sort_column(sort_by: str):
    sort_map = {
        "transaction_date": Transaction.transaction_date,
        "amount": Transaction.amount,
        "type": Transaction.type,
        "category": Transaction.category,
        "created_at": Transaction.created_at,
        "updated_at": Transaction.updated_at,
    }
    return sort_map.get(sort_by, Transaction.transaction_date)