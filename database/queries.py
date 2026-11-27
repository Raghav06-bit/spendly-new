from datetime import datetime
from database.db import get_db


def get_user_by_id(user_id):
    """Return user info dict with name, email, member_since for a given user_id."""
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if not user:
            return None
        # Format member_since as "Month YYYY"
        created_at = user["created_at"]
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                member_since = dt.strftime("%B %Y")
            except ValueError:
                member_since = "Unknown"
        else:
            member_since = "Unknown"
        return {
            "name": user["name"],
            "email": user["email"],
            "member_since": member_since
        }
    finally:
        conn.close()


def get_summary_stats(user_id):
    """Return dict with total_spent, transaction_count, top_category for a user."""
    conn = get_db()
    try:
        # Get total spent and transaction count
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total_spent, COUNT(*) as transaction_count "
            "FROM expenses WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        total_spent = row["total_spent"] or 0
        transaction_count = row["transaction_count"] or 0

        # Get top category by total amount spent
        top_cat_row = conn.execute(
            "SELECT category, SUM(amount) as cat_total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY cat_total DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        top_category = top_cat_row["category"] if top_cat_row else "—"

        return {
            "total_spent": total_spent,
            "transaction_count": transaction_count,
            "top_category": top_category
        }
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10):
    """Return list of recent transactions for a user, newest first."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount "
            "FROM expenses WHERE user_id = ? "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()

        transactions = []
        for row in rows:
            transactions.append({
                "date": row["date"],
                "description": row["description"] or "",
                "category": row["category"],
                "amount": row["amount"]
            })
        return transactions
    finally:
        conn.close()


def get_category_breakdown(user_id):
    """Return list of category breakdown with percentages summing to 100."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY total DESC",
            (user_id,)
        ).fetchall()

        if not rows:
            return []

        # Calculate total across all categories
        grand_total = sum(row["total"] for row in rows)

        # Calculate percentages with integer rounding
        breakdown = []
        for row in rows:
            pct = round((row["total"] / grand_total) * 100) if grand_total > 0 else 0
            breakdown.append({
                "name": row["category"],
                "amount": row["total"],
                "pct": pct
            })

        # Adjust largest category to absorb rounding remainder
        total_pct = sum(item["pct"] for item in breakdown)
        if total_pct != 100 and breakdown:
            diff = 100 - total_pct
            breakdown[0]["pct"] += diff

        return breakdown
    finally:
        conn.close()