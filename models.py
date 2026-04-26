from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)

db = SQLAlchemy()


class User(db.Model):
    """Admin and Staff accounts."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Staff")  # 'Admin' or 'Staff'
    created_at = db.Column(db.DateTime, default=_utcnow)

    sales = db.relationship("Sale", backref="staff", lazy=True)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Item(db.Model):
    """Inventory items — flexible for any shop type."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    sales = db.relationship("Sale", backref="item", lazy=True)

    def __repr__(self):
        return f"<Item {self.name} | {self.category} | stock={self.stock_quantity}>"


class Sale(db.Model):
    """Daily sales / transaction log."""

    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.DateTime, default=_utcnow)
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Sale item_id={self.item_id} qty={self.quantity_sold} total={self.total_price}>"


class ShopProfile(db.Model):
    """Stores the shop's branding / configuration."""

    __tablename__ = "shop_profile"

    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(120), nullable=False, default="My Shop")
    shop_type = db.Column(db.String(80), nullable=True)   # e.g. Laptops, Mobile, Grocery
    logo_path = db.Column(db.String(256), nullable=True)  # relative path inside static/
    address = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<ShopProfile {self.shop_name}>"
