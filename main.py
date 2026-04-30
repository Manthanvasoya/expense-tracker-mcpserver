from fastmcp import FastMCP
import os
import sqlite3
import tempfile

# Try to use the local directory, fallback to /tmp if read-only
DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

# Test if we can write to the target directory
try:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    # Try creating a test file
    test_file = os.path.join(os.path.dirname(DB_PATH), ".write_test")
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)
except (IOError, OSError):
    # Directory is read-only, use /tmp instead
    DB_PATH = os.path.join(tempfile.gettempdir(), "expenses.db")

mcp = FastMCP("ExpenseTracker")

def init_db():
    # Use simple path with WAL mode for better concurrency
    c = sqlite3.connect(DB_PATH, timeout=5.0)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
    """)
    c.commit()
    c.close()

init_db()

@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense entry to the database.'''
    c = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        cur = c.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        c.commit()
        return {"status": "ok", "id": cur.lastrowid}
    finally:
        c.close()
    
@mcp.tool()
def list_expenses(start_date, end_date):
    '''List expense entries within an inclusive date range.'''
    c = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        cur = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        c.close()

@mcp.tool()
def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    c = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        c.close()

@mcp.resource('resource://categories', mime_type="application/json")
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    mcp.run(transport='streamable-http', host='127.0.0.1', port=8002)

