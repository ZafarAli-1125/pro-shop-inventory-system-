"""
app.py — Universal Shop Inventory Management System
Flask entry-point with dynamic SQLite database connection and all core routes.
"""

import os
from functools import wraps
from datetime import datetime, timezone

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Item, Sale, ShopProfile

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app(db_path: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        db_path: Optional absolute or relative path for the SQLite file.
                 Defaults to ``instance/inventory.db`` inside the project root.
                 Pass a different path to point the system at any SQLite file
                 (the 'dynamic database connection logic' requirement).

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=True)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

    # Dynamic database path — allows the shop owner to store the DB on any
    # drive (useful for hardware-locking: keep the DB on a USB key).
    if db_path is None:
        db_path = os.environ.get(
            "DB_PATH",
            os.path.join(app.instance_path, "inventory.db"),
        )

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.abspath(db_path)}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    db.init_app(app)

    # ------------------------------------------------------------------
    # Database initialisation
    # ------------------------------------------------------------------
    with app.app_context():
        db.create_all()
        _seed_defaults()

    # ------------------------------------------------------------------
    # Register routes
    # ------------------------------------------------------------------
    _register_routes(app)

    return app


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------

def _seed_defaults():
    """Create the default admin account and shop profile if they don't exist."""
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="Admin",
        )
        db.session.add(admin)

    if not ShopProfile.query.first():
        profile = ShopProfile(shop_name="My Shop", shop_type="General")
        db.session.add(profile)

    db.session.commit()


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "Admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def _register_routes(app: Flask):

    # ------------------------------------------------------------------ Auth

    @app.route("/", methods=["GET", "POST"])
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password_hash, password):
                session["user_id"] = user.id
                session["username"] = user.username
                session["role"] = user.role
                flash(f"Welcome back, {user.username}!", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid username or password.", "danger")

        profile = ShopProfile.query.first()
        return render_template("login.html", profile=profile)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    # --------------------------------------------------------------- Dashboard

    @app.route("/dashboard")
    @login_required
    def dashboard():
        profile = ShopProfile.query.first()
        total_items = Item.query.count()
        low_stock = Item.query.filter(Item.stock_quantity <= 5).count()
        total_sales = Sale.query.count()

        today = datetime.now(timezone.utc).date()
        today_sales = Sale.query.filter(
            db.func.date(Sale.sale_date) == today
        ).count()

        recent_sales = (
            Sale.query.order_by(Sale.sale_date.desc()).limit(10).all()
        )
        items = Item.query.order_by(Item.name).all()

        return render_template(
            "dashboard.html",
            profile=profile,
            total_items=total_items,
            low_stock=low_stock,
            total_sales=total_sales,
            today_sales=today_sales,
            recent_sales=recent_sales,
            items=items,
        )

    # ------------------------------------------------------------------ Items

    @app.route("/items")
    @login_required
    def items():
        profile = ShopProfile.query.first()
        all_items = Item.query.order_by(Item.category, Item.name).all()
        return render_template("dashboard.html", profile=profile, items=all_items,
                               view="items", total_items=len(all_items),
                               low_stock=sum(1 for i in all_items if i.stock_quantity <= 5),
                               total_sales=Sale.query.count(), today_sales=0,
                               recent_sales=[])

    @app.route("/items/add", methods=["GET", "POST"])
    @login_required
    def add_item():
        if request.method == "POST":
            item = Item(
                name=request.form["name"].strip(),
                category=request.form["category"].strip(),
                price=float(request.form.get("price", 0)),
                stock_quantity=int(request.form.get("stock_quantity", 0)),
                description=request.form.get("description", "").strip(),
            )
            db.session.add(item)
            db.session.commit()
            flash(f'Item "{item.name}" added successfully.', "success")
            return redirect(url_for("dashboard"))
        profile = ShopProfile.query.first()
        return render_template("dashboard.html", profile=profile, view="add_item",
                               items=[], total_items=0, low_stock=0,
                               total_sales=0, today_sales=0, recent_sales=[])

    @app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_item(item_id):
        item = Item.query.get_or_404(item_id)
        if request.method == "POST":
            item.name = request.form["name"].strip()
            item.category = request.form["category"].strip()
            item.price = float(request.form.get("price", item.price))
            item.stock_quantity = int(request.form.get("stock_quantity", item.stock_quantity))
            item.description = request.form.get("description", item.description or "").strip()
            db.session.commit()
            flash(f'Item "{item.name}" updated.', "success")
            return redirect(url_for("dashboard"))
        profile = ShopProfile.query.first()
        return render_template("dashboard.html", profile=profile, view="edit_item",
                               edit_item=item, items=[], total_items=0, low_stock=0,
                               total_sales=0, today_sales=0, recent_sales=[])

    @app.route("/items/<int:item_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def delete_item(item_id):
        item = Item.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        flash(f'Item "{item.name}" deleted.', "success")
        return redirect(url_for("dashboard"))

    # ------------------------------------------------------------------ Sales

    @app.route("/sales/record", methods=["POST"])
    @login_required
    def record_sale():
        item_id = int(request.form["item_id"])
        qty = int(request.form.get("quantity", 1))
        item = Item.query.get_or_404(item_id)

        if item.stock_quantity < qty:
            flash(f"Insufficient stock for {item.name}.", "danger")
            return redirect(url_for("dashboard"))

        sale = Sale(
            item_id=item.id,
            user_id=session["user_id"],
            quantity_sold=qty,
            unit_price=item.price,
            total_price=item.price * qty,
            notes=request.form.get("notes", "").strip(),
        )
        item.stock_quantity -= qty
        db.session.add(sale)
        db.session.commit()
        flash(f"Sale recorded: {qty}× {item.name} for ${sale.total_price:.2f}.", "success")
        return redirect(url_for("dashboard"))

    # ------------------------------------------------------------- Shop Profile

    @app.route("/shop-profile", methods=["GET", "POST"])
    @login_required
    @admin_required
    def shop_profile():
        profile = ShopProfile.query.first()
        if request.method == "POST":
            profile.shop_name = request.form.get("shop_name", profile.shop_name).strip()
            profile.shop_type = request.form.get("shop_type", profile.shop_type or "").strip()
            profile.address = request.form.get("address", profile.address or "").strip()
            profile.phone = request.form.get("phone", profile.phone or "").strip()
            db.session.commit()
            flash("Shop profile updated.", "success")
            return redirect(url_for("dashboard"))

        return render_template("dashboard.html", profile=profile, view="shop_profile",
                               items=[], total_items=Item.query.count(),
                               low_stock=Item.query.filter(Item.stock_quantity <= 5).count(),
                               total_sales=Sale.query.count(), today_sales=0, recent_sales=[])

    # ----------------------------------------------------------- User management

    @app.route("/users")
    @login_required
    @admin_required
    def users():
        profile = ShopProfile.query.first()
        all_users = User.query.order_by(User.username).all()
        return render_template("dashboard.html", profile=profile, view="users",
                               all_users=all_users, items=[],
                               total_items=Item.query.count(),
                               low_stock=Item.query.filter(Item.stock_quantity <= 5).count(),
                               total_sales=Sale.query.count(), today_sales=0, recent_sales=[])

    @app.route("/users/add", methods=["POST"])
    @login_required
    @admin_required
    def add_user():
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form.get("role", "Staff")
        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', "danger")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role=role,
            )
            db.session.add(user)
            db.session.commit()
            flash(f'User "{username}" created as {role}.', "success")
        return redirect(url_for("users"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    flask_app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    flask_app.run(debug=debug, port=5000)
