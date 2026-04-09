"""
Vendor Ordering System for Keil's Service Deli
Generic product catalog + order builder for any vendor.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import json
import uuid


@dataclass
class VendorProduct:
    """A product in a vendor's catalog"""
    id: str
    vendor_id: str
    name: str
    sku: str = ""
    description: str = ""
    category: str = ""
    unit: str = "each"  # each, case, box, bag, roll, etc.
    pack_size: str = ""
    cost: float = 0.0
    is_active: bool = True
    image_url: str = ""  # Product image URL
    item_code: str = ""  # Vendor-specific item code


@dataclass
class VendorOrderItem:
    """An item in a vendor order"""
    product_id: str
    product_name: str
    sku: str
    quantity: int
    unit: str
    cost: float
    total_cost: float


@dataclass
class VendorOrder:
    """An order for a vendor"""
    id: str
    vendor_id: str
    vendor_name: str
    created_at: datetime
    items: List[VendorOrderItem] = field(default_factory=list)
    status: str = "draft"  # draft, submitted, received
    po_number: str = ""
    notes: str = ""
    submitted_at: Optional[datetime] = None

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def total_cost(self) -> float:
        return sum(item.total_cost for item in self.items)


class VendorOrderManager:
    """Manages product catalogs and orders for standard vendors"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.products_file = self.data_dir / "vendor_products.json"
        self.orders_file = self.data_dir / "vendor_orders.json"

    # ---- Products ----

    def load_products(self, vendor_id: str) -> List[VendorProduct]:
        """Load products for a specific vendor"""
        all_products = self._load_all_products()
        return [p for p in all_products if p.vendor_id == vendor_id and p.is_active]

    def get_product(self, product_id: str) -> Optional[VendorProduct]:
        all_products = self._load_all_products()
        return next((p for p in all_products if p.id == product_id), None)

    def add_product(self, product: VendorProduct):
        products = self._load_all_products()
        products.append(product)
        self._save_all_products(products)

    def update_product(self, product_id: str, **kwargs):
        products = self._load_all_products()
        for p in products:
            if p.id == product_id:
                for key, value in kwargs.items():
                    if hasattr(p, key):
                        setattr(p, key, value)
                break
        self._save_all_products(products)

    def delete_product(self, product_id: str):
        products = self._load_all_products()
        products = [p for p in products if p.id != product_id]
        self._save_all_products(products)

    def search_products(self, vendor_id: str, query: str) -> List[VendorProduct]:
        products = self.load_products(vendor_id)
        q = query.lower()
        return [p for p in products if q in p.name.lower() or q in p.sku.lower()
                or q in p.category.lower() or q in p.description.lower()]

    def _load_all_products(self) -> List[VendorProduct]:
        if not self.products_file.exists():
            return []
        try:
            with open(self.products_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [VendorProduct(**item) for item in data]
        except (json.JSONDecodeError, IOError):
            return []

    def _save_all_products(self, products: List[VendorProduct]):
        self.data_dir.mkdir(exist_ok=True)
        data = [
            {
                'id': p.id, 'vendor_id': p.vendor_id, 'name': p.name,
                'sku': p.sku, 'description': p.description, 'category': p.category,
                'unit': p.unit, 'pack_size': p.pack_size, 'cost': p.cost,
                'is_active': p.is_active,
                'image_url': getattr(p, 'image_url', ''),
                'item_code': getattr(p, 'item_code', ''),
            }
            for p in products
        ]
        with open(self.products_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ---- Orders ----

    def get_draft_order(self, vendor_id: str) -> Optional[VendorOrder]:
        orders = self._load_all_orders()
        return next((o for o in orders if o.vendor_id == vendor_id and o.status == 'draft'), None)

    def get_orders(self, vendor_id: str) -> List[VendorOrder]:
        orders = self._load_all_orders()
        return [o for o in orders if o.vendor_id == vendor_id and o.status != 'draft']

    def create_order(self, vendor_id: str, vendor_name: str) -> VendorOrder:
        """Create a new draft order (or return existing draft)"""
        draft = self.get_draft_order(vendor_id)
        if draft:
            return draft
        order = VendorOrder(
            id=str(uuid.uuid4())[:8].upper(),
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            created_at=datetime.now()
        )
        orders = self._load_all_orders()
        orders.append(order)
        self._save_all_orders(orders)
        return order

    def add_item_to_order(self, order_id: str, product: VendorProduct, quantity: int):
        orders = self._load_all_orders()
        for order in orders:
            if order.id == order_id:
                # Check if product already in order
                for item in order.items:
                    if item.product_id == product.id:
                        item.quantity += quantity
                        item.total_cost = item.quantity * item.cost
                        self._save_all_orders(orders)
                        return
                # New item
                order.items.append(VendorOrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    sku=product.sku,
                    quantity=quantity,
                    unit=product.unit,
                    cost=product.cost,
                    total_cost=product.cost * quantity
                ))
                self._save_all_orders(orders)
                return

    def remove_item_from_order(self, order_id: str, product_id: str):
        orders = self._load_all_orders()
        for order in orders:
            if order.id == order_id:
                order.items = [i for i in order.items if i.product_id != product_id]
                self._save_all_orders(orders)
                return

    def submit_order(self, order_id: str, po_number: str = "", notes: str = ""):
        orders = self._load_all_orders()
        for order in orders:
            if order.id == order_id:
                order.status = 'submitted'
                order.po_number = po_number
                order.notes = notes
                order.submitted_at = datetime.now()
                self._save_all_orders(orders)
                return

    def mark_received(self, order_id: str):
        orders = self._load_all_orders()
        for order in orders:
            if order.id == order_id:
                order.status = 'received'
                self._save_all_orders(orders)
                return

    def delete_order(self, order_id: str):
        orders = self._load_all_orders()
        orders = [o for o in orders if o.id != order_id]
        self._save_all_orders(orders)

    def _load_all_orders(self) -> List[VendorOrder]:
        if not self.orders_file.exists():
            return []
        try:
            with open(self.orders_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                orders = []
                for o in data:
                    items = [VendorOrderItem(**i) for i in o.get('items', [])]
                    orders.append(VendorOrder(
                        id=o['id'],
                        vendor_id=o['vendor_id'],
                        vendor_name=o['vendor_name'],
                        created_at=datetime.fromisoformat(o['created_at']),
                        items=items,
                        status=o.get('status', 'draft'),
                        po_number=o.get('po_number', ''),
                        notes=o.get('notes', ''),
                        submitted_at=datetime.fromisoformat(o['submitted_at']) if o.get('submitted_at') else None
                    ))
                return orders
        except (json.JSONDecodeError, IOError):
            return []

    def _save_all_orders(self, orders: List[VendorOrder]):
        self.data_dir.mkdir(exist_ok=True)
        data = [
            {
                'id': o.id, 'vendor_id': o.vendor_id, 'vendor_name': o.vendor_name,
                'created_at': o.created_at.isoformat(),
                'items': [
                    {
                        'product_id': i.product_id, 'product_name': i.product_name,
                        'sku': i.sku, 'quantity': i.quantity, 'unit': i.unit,
                        'cost': i.cost, 'total_cost': i.total_cost
                    }
                    for i in o.items
                ],
                'status': o.status, 'po_number': o.po_number, 'notes': o.notes,
                'submitted_at': o.submitted_at.isoformat() if o.submitted_at else None
            }
            for o in orders
        ]
        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
