"""
KeHE Integration for Keil's Service Deli
Manages KeHE CONNECT ordering and warehouse selection
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import json
import os


class KeHEWarehouse(Enum):
    """KeHE Distribution Centers"""
    DC41 = ("DC41", "DC41")
    DC45 = ("DC45", "DC45")
    
    def __init__(self, code, location):
        self.code = code
        self.location = location


@dataclass
class KeHEProduct:
    """A product available from KeHE"""
    upc: str
    sku: str
    name: str
    brand: str
    category: str
    pack_size: str
    case_cost: float
    unit_cost: float
    units_per_case: int
    warehouse_codes: List[str] = field(default_factory=list)  # Which warehouses stock this
    is_active: bool = True
    last_updated: datetime = field(default_factory=datetime.now)
    in_stock: bool = True  # Track if currently available


@dataclass
class KeHECatalogMeta:
    """Metadata about the KeHE catalog"""
    last_refreshed: Optional[datetime] = None
    total_products: int = 0
    active_products: int = 0


@dataclass
class KeHEOrderItem:
    """An item in a KeHE order"""
    product_sku: str
    product_name: str
    quantity: int  # Number of cases
    case_cost: float
    total_cost: float


@dataclass
class KeHEOrder:
    """A KeHE order"""
    id: str
    created_at: datetime
    warehouse_code: str
    warehouse_name: str
    items: List[KeHEOrderItem] = field(default_factory=list)
    status: str = "draft"  # draft, submitted, confirmed, shipped, delivered
    po_number: str = ""
    notes: str = ""
    submitted_at: Optional[datetime] = None
    
    @property
    def total_cases(self) -> int:
        return sum(item.quantity for item in self.items)
    
    @property
    def total_cost(self) -> float:
        return sum(item.total_cost for item in self.items)


@dataclass
class KeHEConfig:
    """KeHE account configuration"""
    account_number: str = ""
    username: str = ""
    # Note: Password should be stored securely, not in plain text
    primary_warehouse: str = ""
    secondary_warehouses: List[str] = field(default_factory=list)
    auto_reorder: bool = False
    default_delivery_instructions: str = ""


class KeHEManager:
    """Manages KeHE integration"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "kehe_config.json")
        self.products_file = os.path.join(data_dir, "kehe_products.json")
        self.orders_file = os.path.join(data_dir, "kehe_orders.json")
        self.inventory_mapping_file = os.path.join(data_dir, "kehe_inventory_map.json")
        self.catalog_meta_file = os.path.join(data_dir, "kehe_catalog_meta.json")
        
        self._ensure_files()
    
    def _ensure_files(self):
        """Ensure data files exist"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.config_file):
            self.save_config(KeHEConfig())
        
        if not os.path.exists(self.products_file):
            with open(self.products_file, 'w') as f:
                json.dump([], f)
        
        if not os.path.exists(self.orders_file):
            with open(self.orders_file, 'w') as f:
                json.dump([], f)
        
        if not os.path.exists(self.inventory_mapping_file):
            with open(self.inventory_mapping_file, 'w') as f:
                json.dump({}, f)
        
        if not os.path.exists(self.catalog_meta_file):
            self.save_catalog_meta(KeHECatalogMeta())
    
    # ============ Catalog Metadata ============
    
    def load_catalog_meta(self) -> KeHECatalogMeta:
        """Load catalog metadata"""
        try:
            with open(self.catalog_meta_file, 'r') as f:
                data = json.load(f)
                return KeHECatalogMeta(
                    last_refreshed=datetime.fromisoformat(data['last_refreshed']) if data.get('last_refreshed') else None,
                    total_products=data.get('total_products', 0),
                    active_products=data.get('active_products', 0)
                )
        except:
            return KeHECatalogMeta()
    
    def save_catalog_meta(self, meta: KeHECatalogMeta):
        """Save catalog metadata"""
        with open(self.catalog_meta_file, 'w') as f:
            json.dump({
                'last_refreshed': meta.last_refreshed.isoformat() if meta.last_refreshed else None,
                'total_products': meta.total_products,
                'active_products': meta.active_products
            }, f, indent=2)
    
    def refresh_catalog(self) -> Dict:
        """Refresh catalog - marks all products with updated timestamp and updates meta"""
        products = self.load_products()
        now = datetime.now()
        
        # Update all products with refresh timestamp
        for p in products:
            p.last_updated = now
        
        self.save_products(products)
        
        # Update metadata
        meta = KeHECatalogMeta(
            last_refreshed=now,
            total_products=len(products),
            active_products=len([p for p in products if p.is_active and p.in_stock])
        )
        self.save_catalog_meta(meta)
        
        return {
            'refreshed_at': now,
            'total_products': meta.total_products,
            'active_products': meta.active_products
        }
    
    def mark_product_unavailable(self, sku: str):
        """Mark a product as out of stock/unavailable"""
        products = self.load_products()
        for p in products:
            if p.sku == sku:
                p.in_stock = False
                p.last_updated = datetime.now()
                break
        self.save_products(products)
    
    def mark_product_available(self, sku: str):
        """Mark a product as back in stock"""
        products = self.load_products()
        for p in products:
            if p.sku == sku:
                p.in_stock = True
                p.last_updated = datetime.now()
                break
        self.save_products(products)
    
    def deactivate_product(self, sku: str):
        """Deactivate a product (no longer in KeHE catalog)"""
        products = self.load_products()
        for p in products:
            if p.sku == sku:
                p.is_active = False
                p.last_updated = datetime.now()
                break
        self.save_products(products)
    
    def delete_product(self, sku: str):
        """Delete a product from catalog"""
        products = self.load_products()
        products = [p for p in products if p.sku != sku]
        self.save_products(products)
    
    # ============ Configuration ============
    
    def load_config(self) -> KeHEConfig:
        """Load KeHE configuration"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return KeHEConfig(**data)
        except:
            return KeHEConfig()
    
    def save_config(self, config: KeHEConfig):
        """Save KeHE configuration"""
        with open(self.config_file, 'w') as f:
            json.dump({
                'account_number': config.account_number,
                'username': config.username,
                'primary_warehouse': config.primary_warehouse,
                'secondary_warehouses': config.secondary_warehouses,
                'auto_reorder': config.auto_reorder,
                'default_delivery_instructions': config.default_delivery_instructions
            }, f, indent=2)
    
    def get_warehouses(self) -> List[Dict]:
        """Get list of all KeHE warehouses"""
        return [
            {'code': w.code, 'name': w.name, 'location': w.location}
            for w in KeHEWarehouse
        ]
    
    # ============ Product Catalog ============
    
    def load_products(self) -> List[KeHEProduct]:
        """Load KeHE product catalog"""
        try:
            with open(self.products_file, 'r') as f:
                data = json.load(f)
                products = []
                for p in data:
                    products.append(KeHEProduct(
                        upc=p.get('upc', ''),
                        sku=p.get('sku', ''),
                        name=p.get('name', ''),
                        brand=p.get('brand', ''),
                        category=p.get('category', ''),
                        pack_size=p.get('pack_size', ''),
                        case_cost=p.get('case_cost', 0),
                        unit_cost=p.get('unit_cost', 0),
                        units_per_case=p.get('units_per_case', 12),
                        warehouse_codes=p.get('warehouse_codes', []),
                        is_active=p.get('is_active', True),
                        last_updated=datetime.fromisoformat(p['last_updated']) if p.get('last_updated') else datetime.now(),
                        in_stock=p.get('in_stock', True)
                    ))
                return products
        except:
            return []
    
    def save_products(self, products: List[KeHEProduct]):
        """Save KeHE product catalog"""
        with open(self.products_file, 'w') as f:
            json.dump([
                {
                    'upc': p.upc,
                    'sku': p.sku,
                    'name': p.name,
                    'brand': p.brand,
                    'category': p.category,
                    'pack_size': p.pack_size,
                    'case_cost': p.case_cost,
                    'unit_cost': p.unit_cost,
                    'units_per_case': p.units_per_case,
                    'warehouse_codes': p.warehouse_codes,
                    'is_active': p.is_active,
                    'last_updated': p.last_updated.isoformat(),
                    'in_stock': p.in_stock
                }
                for p in products
            ], f, indent=2)
    
    def add_product(self, product: KeHEProduct):
        """Add a product to the catalog"""
        products = self.load_products()
        # Check if product already exists
        for i, p in enumerate(products):
            if p.sku == product.sku:
                products[i] = product
                self.save_products(products)
                return
        products.append(product)
        self.save_products(products)
    
    def import_catalog_csv(self, csv_content: str, warehouse_code: str = None) -> Dict:
        """
        Import products from CSV content.
        Expected columns: SKU, UPC, Name, Brand, Category, Pack Size, Units/Case, Case Cost, Unit Cost
        Returns import statistics.
        """
        import csv
        from io import StringIO
        
        reader = csv.DictReader(StringIO(csv_content))
        products = self.load_products()
        existing_skus = {p.sku for p in products}
        
        added = 0
        updated = 0
        skipped = 0
        errors = []
        
        for row in reader:
            try:
                # Try to find SKU column (various possible names)
                sku = (row.get('SKU') or row.get('sku') or row.get('Item Number') or 
                       row.get('Item #') or row.get('ItemNumber') or row.get('ITEM_NUMBER') or '').strip()
                
                if not sku:
                    skipped += 1
                    continue
                
                # Parse other fields with fallbacks
                name = (row.get('Name') or row.get('name') or row.get('Description') or 
                        row.get('DESCRIPTION') or row.get('Product Name') or row.get('Item Description') or '').strip()
                brand = (row.get('Brand') or row.get('brand') or row.get('BRAND') or 
                         row.get('Vendor') or row.get('Manufacturer') or '').strip()
                upc = (row.get('UPC') or row.get('upc') or row.get('UPC Code') or '').strip()
                category = (row.get('Category') or row.get('category') or row.get('CATEGORY') or 
                           row.get('Department') or '').strip()
                pack_size = (row.get('Pack Size') or row.get('Pack') or row.get('Size') or 
                            row.get('PACK_SIZE') or '').strip()
                
                # Parse numeric fields
                try:
                    units_per_case = int(float(row.get('Units/Case') or row.get('Units Per Case') or 
                                               row.get('Pack Qty') or row.get('UNITS_PER_CASE') or '12'))
                except:
                    units_per_case = 12
                
                try:
                    case_cost = float(row.get('Case Cost') or row.get('Case Price') or 
                                     row.get('CASE_COST') or row.get('Cost') or '0')
                except:
                    case_cost = 0.0
                
                try:
                    unit_cost = float(row.get('Unit Cost') or row.get('Unit Price') or 
                                     row.get('UNIT_COST') or '0')
                except:
                    unit_cost = case_cost / units_per_case if units_per_case > 0 else 0.0
                
                # Determine warehouse codes
                warehouse_codes = []
                if warehouse_code:
                    warehouse_codes = [warehouse_code]
                else:
                    # Try to parse from CSV
                    wh = (row.get('Warehouse') or row.get('DC') or row.get('Distribution Center') or '').strip()
                    if wh:
                        warehouse_codes = [w.strip() for w in wh.split(',')]
                    else:
                        warehouse_codes = ['DC41', 'DC45']  # Default to both
                
                product = KeHEProduct(
                    sku=sku,
                    upc=upc,
                    name=name,
                    brand=brand,
                    category=category,
                    pack_size=pack_size,
                    case_cost=case_cost,
                    unit_cost=unit_cost,
                    units_per_case=units_per_case,
                    warehouse_codes=warehouse_codes,
                    is_active=True,
                    in_stock=True
                )
                
                if sku in existing_skus:
                    # Update existing
                    for i, p in enumerate(products):
                        if p.sku == sku:
                            products[i] = product
                            break
                    updated += 1
                else:
                    products.append(product)
                    existing_skus.add(sku)
                    added += 1
                    
            except Exception as e:
                errors.append(f"Row error: {str(e)}")
                skipped += 1
        
        self.save_products(products)
        
        # Update catalog meta
        meta = KeHECatalogMeta(
            last_refreshed=datetime.now(),
            total_products=len(products),
            active_products=len([p for p in products if p.is_active and p.in_stock])
        )
        self.save_catalog_meta(meta)
        
        return {
            'added': added,
            'updated': updated,
            'skipped': skipped,
            'total': len(products),
            'errors': errors
        }
    
    def clear_catalog(self):
        """Clear all products from catalog"""
        self.save_products([])
        self.save_catalog_meta(KeHECatalogMeta())
    
    def get_product(self, sku: str) -> Optional[KeHEProduct]:
        """Get a product by SKU"""
        products = self.load_products()
        for p in products:
            if p.sku == sku:
                return p
        return None
    
    def search_products(self, query: str, warehouse_code: str = None) -> List[KeHEProduct]:
        """Search products by name, brand, or category"""
        products = self.load_products()
        query = query.lower()
        results = []
        for p in products:
            if (query in p.name.lower() or 
                query in p.brand.lower() or 
                query in p.category.lower()):
                if warehouse_code is None or warehouse_code in p.warehouse_codes:
                    results.append(p)
        return results
    
    def get_products_by_warehouse(self, warehouse_code: str) -> List[KeHEProduct]:
        """Get all products available at a specific warehouse"""
        products = self.load_products()
        return [p for p in products if warehouse_code in p.warehouse_codes]
    
    # ============ Inventory Mapping ============
    
    def load_inventory_mapping(self) -> Dict[str, str]:
        """Load mapping of inventory item IDs to KeHE SKUs"""
        try:
            with open(self.inventory_mapping_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_inventory_mapping(self, mapping: Dict[str, str]):
        """Save inventory mapping"""
        with open(self.inventory_mapping_file, 'w') as f:
            json.dump(mapping, f, indent=2)
    
    def map_inventory_to_kehe(self, inventory_item_id: str, kehe_sku: str):
        """Map an inventory item to a KeHE product"""
        mapping = self.load_inventory_mapping()
        mapping[inventory_item_id] = kehe_sku
        self.save_inventory_mapping(mapping)
    
    def get_kehe_sku_for_item(self, inventory_item_id: str) -> Optional[str]:
        """Get the KeHE SKU for an inventory item"""
        mapping = self.load_inventory_mapping()
        return mapping.get(inventory_item_id)
    
    # ============ Orders ============
    
    def load_orders(self) -> List[KeHEOrder]:
        """Load all KeHE orders"""
        try:
            with open(self.orders_file, 'r') as f:
                data = json.load(f)
                orders = []
                for o in data:
                    items = [KeHEOrderItem(**item) for item in o.get('items', [])]
                    orders.append(KeHEOrder(
                        id=o['id'],
                        created_at=datetime.fromisoformat(o['created_at']),
                        warehouse_code=o['warehouse_code'],
                        warehouse_name=o['warehouse_name'],
                        items=items,
                        status=o.get('status', 'draft'),
                        po_number=o.get('po_number', ''),
                        notes=o.get('notes', ''),
                        submitted_at=datetime.fromisoformat(o['submitted_at']) if o.get('submitted_at') else None
                    ))
                return orders
        except:
            return []
    
    def save_orders(self, orders: List[KeHEOrder]):
        """Save all orders"""
        with open(self.orders_file, 'w') as f:
            json.dump([
                {
                    'id': o.id,
                    'created_at': o.created_at.isoformat(),
                    'warehouse_code': o.warehouse_code,
                    'warehouse_name': o.warehouse_name,
                    'items': [
                        {
                            'product_sku': item.product_sku,
                            'product_name': item.product_name,
                            'quantity': item.quantity,
                            'case_cost': item.case_cost,
                            'total_cost': item.total_cost
                        }
                        for item in o.items
                    ],
                    'status': o.status,
                    'po_number': o.po_number,
                    'notes': o.notes,
                    'submitted_at': o.submitted_at.isoformat() if o.submitted_at else None
                }
                for o in orders
            ], f, indent=2)
    
    def create_order(self, warehouse_code: str) -> KeHEOrder:
        """Create a new order"""
        config = self.load_config()
        
        # Find warehouse name
        warehouse_name = warehouse_code
        for w in KeHEWarehouse:
            if w.code == warehouse_code:
                warehouse_name = f"{w.location}"
                break
        
        order = KeHEOrder(
            id=f"KEHE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            created_at=datetime.now(),
            warehouse_code=warehouse_code,
            warehouse_name=warehouse_name
        )
        
        orders = self.load_orders()
        orders.append(order)
        self.save_orders(orders)
        
        return order
    
    def get_order(self, order_id: str) -> Optional[KeHEOrder]:
        """Get an order by ID"""
        orders = self.load_orders()
        for o in orders:
            if o.id == order_id:
                return o
        return None
    
    def add_item_to_order(self, order_id: str, sku: str, quantity: int) -> bool:
        """Add an item to an order"""
        orders = self.load_orders()
        product = self.get_product(sku)
        
        if not product:
            return False
        
        for order in orders:
            if order.id == order_id:
                # Check if item already in order
                for item in order.items:
                    if item.product_sku == sku:
                        item.quantity += quantity
                        item.total_cost = item.quantity * item.case_cost
                        self.save_orders(orders)
                        return True
                
                # Add new item
                order.items.append(KeHEOrderItem(
                    product_sku=sku,
                    product_name=product.name,
                    quantity=quantity,
                    case_cost=product.case_cost,
                    total_cost=quantity * product.case_cost
                ))
                self.save_orders(orders)
                return True
        
        return False
    
    def remove_item_from_order(self, order_id: str, sku: str) -> bool:
        """Remove an item from an order"""
        orders = self.load_orders()
        
        for order in orders:
            if order.id == order_id:
                order.items = [i for i in order.items if i.product_sku != sku]
                self.save_orders(orders)
                return True
        
        return False
    
    def update_order_status(self, order_id: str, status: str, po_number: str = None):
        """Update order status"""
        orders = self.load_orders()
        
        for order in orders:
            if order.id == order_id:
                order.status = status
                if status == 'submitted':
                    order.submitted_at = datetime.now()
                if po_number:
                    order.po_number = po_number
                self.save_orders(orders)
                return True
        
        return False
    
    def delete_order(self, order_id: str) -> bool:
        """Delete a draft order"""
        orders = self.load_orders()
        orders = [o for o in orders if o.id != order_id]
        self.save_orders(orders)
        return True
    
    def get_draft_order(self) -> Optional[KeHEOrder]:
        """Get the current draft order if one exists"""
        orders = self.load_orders()
        for o in orders:
            if o.status == 'draft':
                return o
        return None
    
    def generate_order_csv(self, order_id: str) -> str:
        """Generate CSV content for an order (for upload to KeHE CONNECT)"""
        order = self.get_order(order_id)
        if not order:
            return ""
        
        lines = ["SKU,Product Name,Quantity,Case Cost,Total"]
        for item in order.items:
            lines.append(f"{item.product_sku},{item.product_name},{item.quantity},{item.case_cost:.2f},{item.total_cost:.2f}")
        
        lines.append(f"")
        lines.append(f"Total Cases:,{order.total_cases}")
        lines.append(f"Total Cost:,${order.total_cost:.2f}")
        
        return "\n".join(lines)
