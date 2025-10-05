from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re
import os
from dotenv import load_dotenv
from datetime import datetime
import calendar
from flask_login import login_required
from flask_login import LoginManager
from flask_login import login_user 
from flask_login import login_required, current_user 
from flask_login import logout_user
from models import User  


# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key")
DATABASE = r'C:\SET\Smart Expense Tracker\database\smartexpense.db'

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM User WHERE UserID = ?", (user_id,))
    user_row = cursor.fetchone()
    if user_row:
        return User(user_row)
    return None


def get_db():
    if not hasattr(g, 'sqlite_db'):
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        g.sqlite_db = db
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first-name']
        last_name = request.form['last-name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        account_type = request.form['account-type']

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('signup'))

        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, email):
            flash("Invalid email format!", "error")
            return redirect(url_for('signup'))

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM User WHERE Username = ? OR Email = ?", (username, email))
            if cursor.fetchone():
                flash("Username or email already exists!", "error")
                return redirect(url_for('signup'))

            cursor.execute("""
                INSERT INTO User (FirstName, LastName, AccountType, Username, Email, Password)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (first_name, last_name, account_type, username, email, hashed_password))
            db.commit()
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            flash(f"Database error: {e}", "error")
            return redirect(url_for('signup'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM User WHERE Username = ?", (username,))
        user_row = cursor.fetchone()
        
        if user_row and check_password_hash(user_row['Password'], password):
            user = User(user_row)  # Create a User instance
            login_user(user)  # Log the user in
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        
        flash("Invalid credentials.", "error")
        return redirect(url_for('login'))
    
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor()

    # Get latest budget for user
    cursor.execute("""
        SELECT BudgetID, AccountLimit, Month, Year
        FROM Budget WHERE UserID = ?
        ORDER BY Year DESC, Month DESC LIMIT 1
    """, (current_user.id,))  # ✅ use current_user.id
    latest_budget = cursor.fetchone()

    expenses = []
    categories = []
    transactions = []
    reward_total = 0
    category_totals = []

    if latest_budget:
        month = latest_budget['Month']
        month_name = calendar.month_name[int(month)] if month else "N/A"
        latest_budget = dict(latest_budget)
        latest_budget['MonthName'] = month_name

        # Get transactions
        cursor.execute("""
            SELECT Amount, Date, Category, Description
            FROM "Transaction"
            WHERE BudgetID = ?
            ORDER BY Date DESC
        """, (latest_budget['BudgetID'],))
        transactions = cursor.fetchall()

        total_transactions = sum([row['Amount'] for row in transactions])
        latest_budget['TotalTransactions'] = total_transactions

        # Reward logic
        current_date = datetime.today()
        budget_year = int(latest_budget['Year'])
        budget_month = int(latest_budget['Month'])

        if budget_year < current_date.year or (budget_year == current_date.year and budget_month < current_date.month):
            cursor.execute("""
                SELECT 1 FROM Rewards
                WHERE RewardID = ? AND UserID = ?
            """, (latest_budget['BudgetID'], current_user.id))
            reward_exists = cursor.fetchone()

            if not reward_exists:
                reward_amount = 0.10
                if total_transactions <= float(latest_budget['AccountLimit']):
                    unused = float(latest_budget['AccountLimit']) - total_transactions
                    reward_amount += round(unused * 0.05, 2)

                cursor.execute("""
                    INSERT INTO Rewards (RewardID, UserID, Amount)
                    VALUES (?, ?, ?)
                """, (latest_budget['BudgetID'], current_user.id, reward_amount))
                db.commit()

        # Expenses and category totals
        cursor.execute("""
            SELECT Amount, Category FROM Expense WHERE BudgetID = ?
        """, (latest_budget['BudgetID'],))
        expenses = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT Category FROM Expense WHERE BudgetID = ?
        """, (latest_budget['BudgetID'],))
        categories = [row['Category'].capitalize() for row in cursor.fetchall()]

        cursor.execute("""
            SELECT Category, SUM(Amount) AS TotalAmount
            FROM Expense
            WHERE BudgetID = ?
            GROUP BY Category
        """, (latest_budget['BudgetID'],))
        category_totals = cursor.fetchall()

    # Total rewards
    cursor.execute("""
        SELECT COALESCE(SUM(Amount), 0) AS total FROM Rewards
        WHERE UserID = ?
    """, (current_user.id,))
    reward_row = cursor.fetchone()
    reward_total = reward_row['total'] if reward_row else 0

    return render_template('dashboard.html',
                           first_name=current_user.first_name.capitalize(),
                           last_name=current_user.last_name.capitalize(),
                           latest_budget=latest_budget,
                           expenses=expenses,
                           categories=categories,
                           transactions=transactions,
                           reward_total=reward_total,
                           category_totals=category_totals)




@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


@app.route('/create_budget', methods=['GET', 'POST'])
def create_budget():
    if request.method == 'POST':
        account_limit = request.form['account_limit']
        month = request.form['month']
        year = request.form['year']
        income = request.form['income']
        total_expenses = int(request.form['total_expenses'])

        if not account_limit or not month or not year or not income:
            flash("All fields are required.", "error")
            return redirect(url_for('create_budget'))

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO Budget (UserID, AccountLimit, Month, Year, Income)
                VALUES (?, ?, ?, ?, ?)
            """, (current_user.id, account_limit, month, year, income))
            db.commit()
            budget_id = cursor.lastrowid

            for i in range(1, total_expenses + 1):
                category = request.form.get(f'Category{i}')
                amount_str = request.form.get(f'expense_amount_{i}')
                if category and amount_str and amount_str.strip():
                    try:
                        amount = float(amount_str)
                        cursor.execute("""
                            INSERT INTO Expense (BudgetID, Category, Amount)
                            VALUES (?, ?, ?)
                        """, (budget_id, category, amount))
                    except ValueError:
                        flash(f"Invalid amount for category '{category}'. Please enter a valid number.", "error")
                        db.rollback()
                        return redirect(url_for('create_budget'))

            db.commit()
            db.close()

            flash("Budget and expenses created successfully!", "success")
            return redirect(url_for('dashboard'))

        except sqlite3.Error as e:
            db.rollback()
            db.close()
            flash(f"Error creating budget: {e}", "error")
            return redirect(url_for('create_budget'))

    return render_template('create_budget.html')

@app.route('/add_expense', methods=['POST'])
def add_expense():
    category = request.form['Category']
    other_category = request.form.get('OtherCategory')
    amount = float(request.form['expense_amount'])
    budget_id = request.form['budget_id']

    # Use the custom category if 'Other' is selected
    if category == 'Other' and other_category:
        category = other_category

    try:
        db = get_db()
        cursor = db.cursor()

        # 1. Get current total of expenses for this budget
        cursor.execute("""
            SELECT SUM(Amount) as Total FROM Expense
            WHERE BudgetID = ?
        """, (budget_id,))
        result = cursor.fetchone()
        current_expenses = result['Total'] if result and result['Total'] else 0

        # 2. Get the budget limit
        cursor.execute("SELECT AccountLimit FROM Budget WHERE BudgetID = ?", (budget_id,))
        budget = cursor.fetchone()
        if not budget:
            flash("Budget not found.", "error")
            return redirect(url_for('dashboard'))

        account_limit = float(budget['AccountLimit'])

        # 3. Check if adding this expense would exceed the budget
        if current_expenses + amount > account_limit:
            flash("⚠️ This expense would exceed your overall account limit!", "warning")
            return redirect(url_for('dashboard'))

        # 4. Insert the expense
        cursor.execute("""
            INSERT INTO Expense (BudgetID, Category, Amount)
            VALUES (?, ?, ?)
        """, (budget_id, category, amount))
        db.commit()

        flash("Expense added successfully!", "success")

    except sqlite3.Error as e:
        db.rollback()
        flash(f"Error adding expense: {e}", "error")
    finally:
        db.close()
    
    return redirect(url_for('dashboard'))


@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    description = request.form['transaction_description']
    category = request.form['Category']
    amount = float(request.form['transaction_amount'])
    date = request.form['transaction_date']
    budget_id = request.form['budget_id']

    try:
        db = get_db()
        cursor = db.cursor()

        # 1. Get budget info
        cursor.execute("SELECT AccountLimit FROM Budget WHERE BudgetID = ?", (budget_id,))
        budget = cursor.fetchone()
        if not budget:
            flash("Budget not found.", "error")
            return redirect(url_for('dashboard'))

        account_limit = float(budget['AccountLimit'])

        # 2. Get total transactions so far
        cursor.execute("""
            SELECT SUM(Amount) as Total FROM "Transaction"
            WHERE BudgetID = ?
        """, (budget_id,))
        result = cursor.fetchone()
        current_total = result['Total'] if result and result['Total'] else 0

        # Check if new transaction would exceed total budget
        if current_total + amount > account_limit:
            flash("⚠️ This transaction would exceed your overall account limit!", "warning")
            return redirect(url_for('dashboard'))  # 🚫 STOP

        # 3. Check category limit
        cursor.execute("""
            SELECT SUM(Amount) as Total FROM "Transaction"
            WHERE BudgetID = ? AND Category = ?
        """, (budget_id, category))
        result = cursor.fetchone()
        category_total = result['Total'] if result and result['Total'] else 0

        cursor.execute("""
            SELECT Amount FROM Expense
            WHERE BudgetID = ? AND Category = ?
        """, (budget_id, category))
        expense = cursor.fetchone()
        if expense:
            category_limit = float(expense['Amount'])
            if category_total + amount > category_limit:
                flash(f"⚠️ This transaction would exceed your budget for the '{category}' category!", "warning")
                return redirect(url_for('dashboard'))  # 🚫 STOP
        else:
            flash(f"⚠️ No defined expense for '{category}'.", "warning")
            return redirect(url_for('dashboard'))  # 🚫 STOP

        # 4. Insert transaction
        cursor.execute("""
            INSERT INTO "Transaction" (Description, Category, Amount, Date, BudgetID)
            VALUES (?, ?, ?, ?, ?)
        """, (description, category, amount, date, budget_id))
        db.commit()

        # 5. Update total transactions in Budget table and shows result
        cursor.execute("""
            SELECT SUM(Amount) as Total FROM "Transaction"
            WHERE BudgetID = ?
        """, (budget_id,))
        total_result = cursor.fetchone()
        total_transactions = total_result['Total'] if total_result and total_result['Total'] else 0

        cursor.execute("""
            UPDATE Budget SET TotalTransactions = ?
            WHERE BudgetID = ?
        """, (total_transactions, budget_id))
        db.commit()

        flash("Transaction added successfully!", "success")
        return redirect(url_for('dashboard'))

    except sqlite3.Error as e:
        db.rollback()
        flash(f"Error adding transaction: {e}", "error")
        return redirect(url_for('dashboard'))
    
@app.route('/history')
@login_required
def history():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT               -- ← added BudgetID
            b.BudgetID,
            b.Month,
            b.Year,
            b.AccountLimit,
            COALESCE(SUM(t.Amount), 0) AS TotalTransactions
        FROM Budget b
        LEFT JOIN "Transaction" t ON b.BudgetID = t.BudgetID
        WHERE b.UserID = ?
        GROUP BY b.BudgetID
        ORDER BY b.Year DESC, b.Month DESC
    """, (current_user.id,))

    budget_rows = cursor.fetchall()

    budget_history = []
    for row in budget_rows:
        row = dict(row)
        row['MonthName'] = calendar.month_name[int(row['Month'])] if row['Month'] else "Unknown"
        budget_history.append(row)

    return render_template("history.html", budget_history=budget_history)


@app.route('/history/<int:budget_id>')
@login_required
def view_budget_charts(budget_id):
    db = get_db()
    cursor = db.cursor()

    # Get budget info
    cursor.execute("""
        SELECT * FROM Budget
        WHERE BudgetID = ? AND UserID = ?
    """, (budget_id, current_user.id))  # ✅ use current_user.id

    budget = cursor.fetchone()
    if not budget:
        flash("Budget not found.", "error")
        return redirect(url_for('history'))

    budget = dict(budget)
    budget['MonthName'] = calendar.month_name[int(budget['Month'])]

    # Get expenses for pie chart
    cursor.execute("""
        SELECT Category, Amount FROM Expense WHERE BudgetID = ?
    """, (budget_id,))
    expenses = cursor.fetchall()

    # Get transactions for bar chart
    cursor.execute("""
        SELECT Category, SUM(Amount) AS Total
        FROM "Transaction"
        WHERE BudgetID = ?
        GROUP BY Category
    """, (budget_id,))
    transactions = cursor.fetchall()

    return render_template('budget_charts.html',
                           budget=budget,
                           expenses=expenses,
                           transactions=transactions)

if __name__ == '__main__':
    app.run(debug=True)
