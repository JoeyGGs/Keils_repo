"""
Order Sheet Generation for Keil's Service Deli
"""

from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path

from src.models import InventoryItem, ItemCategory
from src.vendors import Vendor, VendorManager


class OrderSheetGenerator:
    def __init__(self, inventory_items: List[InventoryItem]):
        self.items = inventory_items
        self.vendor_manager = VendorManager()
    
    def get_items_to_order(self) -> List[InventoryItem]:
        """Get all items that need to be ordered (at or below min quantity)"""
        return [item for item in self.items if item.is_low_stock]
    
    def get_suggested_order_quantity(self, item: InventoryItem) -> float:
        """Calculate suggested order quantity (2x minimum as default)"""
        target = item.min_quantity * 2
        needed = target - item.quantity
        return max(0, needed)
    
    def generate_order_by_vendor(self, vendor_id: str) -> Dict:
        """Generate order sheet for a specific vendor"""
        vendor = self.vendor_manager.get_vendor(vendor_id)
        if not vendor:
            return None
        
        # Get items that match vendor's categories and need ordering
        vendor_items = []
        for item in self.items:
            if item.category.name in vendor.categories:
                if item.is_low_stock or item.quantity < item.min_quantity * 1.5:
                    suggested_qty = self.get_suggested_order_quantity(item)
                    if suggested_qty > 0:
                        vendor_items.append({
                            'item': item,
                            'suggested_quantity': suggested_qty,
                            'estimated_cost': suggested_qty * item.cost_per_unit
                        })
        
        return {
            'vendor': vendor,
            'items': vendor_items,
            'generated_date': datetime.now(),
            'total_estimated_cost': sum(i['estimated_cost'] for i in vendor_items)
        }
    
    def generate_all_orders(self) -> List[Dict]:
        """Generate order sheets for all vendors with items to order"""
        orders = []
        for vendor in self.vendor_manager.get_all_vendors():
            order = self.generate_order_by_vendor(vendor.id)
            if order and order['items']:
                orders.append(order)
        return orders
    
    def generate_order_html(self, vendor_id: str) -> str:
        """Generate printable HTML order sheet for a vendor"""
        order = self.generate_order_by_vendor(vendor_id)
        if not order or not order['items']:
            return "<p>No items to order from this vendor.</p>"
        
        vendor = order['vendor']
        html = f"""
        <div class="order-sheet printable">
            <div class="order-header">
                <h2>KEIL'S SERVICE DELI</h2>
                <h3>Purchase Order</h3>
                <p>Date: {order['generated_date'].strftime('%B %d, %Y')}</p>
            </div>
            
            <div class="vendor-info">
                <h4>Vendor: {vendor.name}</h4>
                <p>Phone: {vendor.phone or 'N/A'}</p>
                <p>Email: {vendor.email or 'N/A'}</p>
                <p>Contact: {vendor.contact_name or 'N/A'}</p>
            </div>
            
            <table class="order-table">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Category</th>
                        <th>Current Stock</th>
                        <th>Order Qty</th>
                        <th>Unit</th>
                        <th>Est. Cost</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for item_data in order['items']:
            item = item_data['item']
            html += f"""
                    <tr>
                        <td>{item.name}</td>
                        <td>{item.category.value}</td>
                        <td>{item.quantity:.1f}</td>
                        <td><input type="number" value="{item_data['suggested_quantity']:.1f}" class="order-qty"></td>
                        <td>{item.unit}</td>
                        <td>${item_data['estimated_cost']:.2f}</td>
                    </tr>
            """
        
        html += f"""
                </tbody>
                <tfoot>
                    <tr>
                        <td colspan="5" class="text-right"><strong>Estimated Total:</strong></td>
                        <td><strong>${order['total_estimated_cost']:.2f}</strong></td>
                    </tr>
                </tfoot>
            </table>
            
            <div class="order-footer">
                <div class="signature-line">
                    <p>Ordered By: _______________________</p>
                    <p>Date: _______________________</p>
                </div>
                <div class="notes">
                    <p>Notes: {vendor.notes}</p>
                </div>
            </div>
        </div>
        """
        return html
