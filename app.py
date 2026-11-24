
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "student-task-manager-secret"

DATABASE = "tasks.db"

CATEGORIES = ["College", "Personal", "Projects", "Exams"]
PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["To Do", "In Progress", "Completed"]


# Database connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Create and upgrade database
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            completed INTEGER DEFAULT 0
        )
    """)

    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    ]

    new_columns = {
        "priority": "TEXT DEFAULT 'Medium'",
        "category": "TEXT DEFAULT 'College'",
        "status": "TEXT DEFAULT 'To Do'"
    }

    for column, definition in new_columns.items():
        if column not in columns:
            conn.execute(
                f"ALTER TABLE tasks ADD COLUMN {column} {definition}"
            )

    conn.execute("""
        UPDATE tasks
        SET status = CASE
            WHEN completed = 1 THEN 'Completed'
            ELSE 'To Do'
        END
        WHERE status IS NULL OR status = ''
    """)

    conn.commit()
    conn.close()


# Dashboard
@app.route("/")
def index():
    conn = get_db()

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    category_filter = request.args.get("category", "")

    sql = "SELECT * FROM tasks WHERE 1=1"
    values = []

    if search:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        values.extend([f"%{search}%", f"%{search}%"])

    if status_filter in STATUSES:
        sql += " AND status = ?"
        values.append(status_filter)

    if priority_filter in PRIORITIES:
        sql += " AND priority = ?"
        values.append(priority_filter)

    if category_filter in CATEGORIES:
        sql += " AND category = ?"
        values.append(category_filter)

    sql += """
        ORDER BY
        CASE priority
            WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2
            ELSE 3
        END,
        due_date ASC,
        id DESC
    """

    tasks = conn.execute(sql, values).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]

    completed = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Completed'"
    ).fetchone()[0]

    in_progress = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'In Progress'"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'To Do'"
    ).fetchone()[0]

    today = date.today().isoformat()

    overdue_tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE due_date < ?
        AND due_date IS NOT NULL
        AND due_date != ''
        AND status != 'Completed'
        ORDER BY due_date ASC
    """, (today,)).fetchall()

    due_today = conn.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE due_date = ?
        AND status != 'Completed'
    """, (today,)).fetchone()[0]

    upcoming = conn.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE due_date > ?
        AND due_date <= date(?, '+3 days')
        AND status != 'Completed'
    """, (today, today)).fetchone()[0]

    conn.close()

    progress = round((completed / total) * 100) if total else 0

    return render_template(
        "index.html",
        tasks=tasks,
        total=total,
        completed=completed,
        pending=pending,
        in_progress=in_progress,
        overdue=len(overdue_tasks),
        overdue_tasks=overdue_tasks,
        due_today=due_today,
        upcoming=upcoming,
        progress=progress,
        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter,
        category_filter=category_filter,
        categories=CATEGORIES,
        priorities=PRIORITIES,
        statuses=STATUSES,
        today=today
    )


# Add task
@app.route("/add", methods=["POST"])
def add_task():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "")
    priority = request.form.get("priority", "Medium")
    category = request.form.get("category", "College")

    if not title:
        flash("Please enter a task title.", "error")
        return redirect(url_for("index"))

    if priority not in PRIORITIES:
        priority = "Medium"

    if category not in CATEGORIES:
        category = "College"

    conn = get_db()

    conn.execute("""
        INSERT INTO tasks
        (title, description, due_date, priority, category, status, completed)
        VALUES (?, ?, ?, ?, ?, 'To Do', 0)
    """, (title, description, due_date, priority, category))

    conn.commit()
    conn.close()

    flash("Task added successfully!", "success")
    return redirect(url_for("index"))


# Edit task
@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    conn = get_db()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()

    if task is None:
        conn.close()
        flash("Task not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "")
        priority = request.form.get("priority", "Medium")
        category = request.form.get("category", "College")
        status = request.form.get("status", "To Do")

        if not title:
            conn.close()
            flash("Task title cannot be empty.", "error")
            return redirect(url_for("edit_task", task_id=task_id))

        if priority not in PRIORITIES:
            priority = "Medium"

        if category not in CATEGORIES:
            category = "College"

        if status not in STATUSES:
            status = "To Do"

        completed = 1 if status == "Completed" else 0

        conn.execute("""
            UPDATE tasks
            SET title = ?, description = ?, due_date = ?,
                priority = ?, category = ?, status = ?, completed = ?
            WHERE id = ?
        """, (
            title, description, due_date,
            priority, category, status, completed, task_id
        ))

        conn.commit()
        conn.close()

        flash("Task updated successfully!", "success")
        return redirect(url_for("index"))

    conn.close()

    return render_template(
        "edit.html",
        task=task,
        categories=CATEGORIES,
        priorities=PRIORITIES,
        statuses=STATUSES
    )


# Update task status
@app.route("/status/<int:task_id>", methods=["POST"])
def update_status(task_id):
    status = request.form.get("status", "To Do")

    if status not in STATUSES:
        status = "To Do"

    completed = 1 if status == "Completed" else 0

    conn = get_db()

    conn.execute("""
        UPDATE tasks
        SET status = ?, completed = ?
        WHERE id = ?
    """, (status, completed, task_id))

    conn.commit()
    conn.close()

    flash("Task status updated.", "success")
    return redirect(url_for("index"))


# Delete task
@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    conn = get_db()

    conn.execute(
        "DELETE FROM tasks WHERE id = ?", (task_id,)
    )

    conn.commit()
    conn.close()

    flash("Task deleted successfully!", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
