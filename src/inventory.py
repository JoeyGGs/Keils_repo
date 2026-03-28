"""
Inventory Management Module for Keil's Service Deli
"""

from datetime import datetime, date
from typing import List, Optional
import json

from src.models import InventoryItem, ItemCategory, DailyUsage
from src.data_store import DataStore


class InventoryManager:
    def __init__(self):
        self.data_store = DataStore()
        self._load_data()
    
    def _load_data(self):
        """Load inventory from storage"""
        self.items = self.data_store.load_inventory()
        self.usage_log = self.data_store.load_usage_log()
    
    def _save_data(self):
        """Save inventory to storage"""
        self.data_store.save_inventory(self.items)
        self.data_store.save_usage_log(self.usage_log)
    
    def view_inventory(self):
        """Display all inventory items grouped by category"""
        print(f"\n{'=' * 60}")
        print("   INVENTORY - KEIL'S SERVICE DELI")
        print(f"{'=' * 60}")
        
        if not self.items:
            print("\nNo items in inventory. Add items to get started.")
            return
        
        # Group by category
        by_category = {}
        for item in self.items:
            cat_name = item.category.value
            if cat_name not in by_category:
                by_category[cat_name] = []
            by_category[cat_name].append(item)
        
        for category, items in sorted(by_category.items()):
            print(f"\n{category}:")
            print("-" * 50)
            print(f"  {'Item':<25} {'Qty':>8} {'Unit':<10} {'Status':<10}")
            print("-" * 50)
            
            for item in sorted(items, key=lambda x: x.name):
                status = "⚠ LOW" if item.is_low_stock else "OK"
                print(f"  {item.name:<25} {item.quantity:>8.1f} {item.unit:<10} {status:<10}")
        
        print(f"\n{'=' * 60}")
        total_items = len(self.items)
        low_stock = len([i for i in self.items if i.is_low_stock])
        print(f"Total Items: {total_items} | Low Stock Alerts: {low_stock}")
    
    def add_item(self):
        """Add a new item to inventory"""
        print("\n--- Add New Inventory Item ---")
        
        name = input("Item name: ").strip()
        if not name:
            print("Name is required.")
            return
        
        # Check for duplicate
        if any(i.name.lower() == name.lower() for i in self.items):
            print(f"Item '{name}' already exists. Use 'Update Quantity' instead.")
            return
        
        # Select category
        print("\nCategories:")
        for i, cat in enumerate(ItemCategory, 1):
            print(f"  {i}. {cat.value}")
        
        try:
            cat_choice = int(input("\nSelect category: ")) - 1
            category = list(ItemCategory)[cat_choice]
        except (ValueError, IndexError):
            print("Invalid selection. Using 'Other'.")
            category = ItemCategory.OTHER
        
        unit = input("Unit of measurement (e.g., lbs, each, gallons): ").strip() or "each"
        
        try:
            quantity = float(input("Current quantity: ").strip() or "0")
            min_quantity = float(input("Minimum quantity (reorder level): ").strip() or "5")
            cost = float(input("Cost per unit (optional, $): ").strip() or "0")
        except ValueError:
            print("Invalid number. Please try again.")
            return
        
        supplier = input("Supplier (optional): ").strip()
        notes = input("Notes (optional): ").strip()
        
        item_id = f"INV{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_item = InventoryItem(
            id=item_id,
            name=name,
            category=category,
            quantity=quantity,
            unit=unit,
            min_quantity=min_quantity,
            cost_per_unit=cost,
            supplier=supplier,
            notes=notes
        )
        
        self.items.append(new_item)
        self._save_data()
        print(f"\n✓ '{name}' added to inventory")
        
        if new_item.is_low_stock:
            print(f"⚠ Warning: Item is below minimum quantity ({min_quantity} {unit})")
    
    def update_quantity(self):
        """Update quantity of an existing item"""
        print("\n--- Update Item Quantity ---")
        
        if not self.items:
            print("\nNo items in inventory.")
            return
        
        # Search for item
        search = input("Search for item (or press Enter to list all): ").strip()
        
        if search:
            matches = [i for i in self.items if search.lower() in i.name.lower()]
        else:
            matches = self.items
        
        if not matches:
            print(f"\nNo items found matching '{search}'")
            return
        
        print("\nMatching Items:")
        for i, item in enumerate(matches, 1):
            print(f"  {i}. {item.name} - Current: {item.quantity} {item.unit}")
        
        try:
            choice = int(input("\nSelect item to update: ")) - 1
            if choice < 0 or choice >= len(matches):
                print("Invalid selection.")
                return
            item = matches[choice]
        except ValueError:
            print("Invalid input.")
            return
        
        print(f"\nCurrent quantity: {item.quantity} {item.unit}")
        print("Options:")
        print("  1. Set new quantity")
        print("  2. Add to quantity")
        print("  3. Subtract from quantity")
        
        action = input("\nSelect option: ").strip()
        
        try:
            if action == "1":
                new_qty = float(input("Enter new quantity: "))
                item.quantity = new_qty
            elif action == "2":
                add_qty = float(input("Quantity to add: "))
                item.quantity += add_qty
            elif action == "3":
                sub_qty = float(input("Quantity to subtract: "))
                item.quantity = max(0, item.quantity - sub_qty)
            else:
                print("Invalid option.")
                return
        except ValueError:
            print("Invalid number.")
            return
        
        item.last_updated = datetime.now()
        self._save_data()
        print(f"\n✓ '{item.name}' updated. New quantity: {item.quantity} {item.unit}")
        
        if item.is_low_stock:
            print(f"⚠ Warning: Item is below minimum quantity ({item.min_quantity} {item.unit})")
    
    def remove_item(self):
        """Remove an item from inventory"""
        print("\n--- Remove Inventory Item ---")
        
        if not self.items:
            print("\nNo items in inventory.")
            return
        
        search = input("Search for item to remove: ").strip()
        
        if not search:
            print("Please enter a search term.")
            return
        
        matches = [i for i in self.items if search.lower() in i.name.lower()]
        
        if not matches:
            print(f"\nNo items found matching '{search}'")
            return
        
        print("\nMatching Items:")
        for i, item in enumerate(matches, 1):
            print(f"  {i}. {item.name} ({item.category.value})")
        
        try:
            choice = int(input("\nSelect item to remove (0 to cancel): "))
            if choice == 0:
                return
            if choice < 1 or choice > len(matches):
                print("Invalid selection.")
                return
            
            item = matches[choice - 1]
            confirm = input(f"Are you sure you want to remove '{item.name}'? (y/n): ").strip().lower()
            
            if confirm == 'y':
                self.items.remove(item)
                self._save_data()
                print(f"\n✓ '{item.name}' removed from inventory")
            else:
                print("Cancelled.")
        except ValueError:
            print("Invalid input.")
    
    def check_low_stock(self):
        """Display items that are below minimum quantity"""
        print(f"\n{'=' * 50}")
        print("   LOW STOCK ALERT")
        print(f"{'=' * 50}")
        
        low_items = [i for i in self.items if i.is_low_stock]
        
        if not low_items:
            print("\n✓ All items are adequately stocked!")
            return
        
        print(f"\n⚠ {len(low_items)} item(s) need attention:\n")
        print(f"  {'Item':<25} {'Current':>10} {'Minimum':>10} {'Unit':<10}")
        print("-" * 60)
        
        for item in sorted(low_items, key=lambda x: x.quantity / x.min_quantity):
            print(f"  {item.name:<25} {item.quantity:>10.1f} {item.min_quantity:>10.1f} {item.unit:<10}")
            if item.supplier:
                print(f"    Supplier: {item.supplier}")
        
        print(f"\n{'=' * 50}")
    
    def record_usage(self):
        """Record daily usage of an item"""
        print("\n--- Record Daily Usage ---")
        
        if not self.items:
            print("\nNo items in inventory.")
            return
        
        search = input("Search for item: ").strip()
        
        if not search:
            print("Please enter a search term.")
            return
        
        matches = [i for i in self.items if search.lower() in i.name.lower()]
        
        if not matches:
            print(f"\nNo items found matching '{search}'")
            return
        
        print("\nMatching Items:")
        for i, item in enumerate(matches, 1):
            print(f"  {i}. {item.name} - Current: {item.quantity} {item.unit}")
        
        try:
            choice = int(input("\nSelect item: ")) - 1
            if choice < 0 or choice >= len(matches):
                print("Invalid selection.")
                return
            item = matches[choice]
        except ValueError:
            print("Invalid input.")
            return
        
        try:
            qty_used = float(input(f"Quantity used ({item.unit}): "))
        except ValueError:
            print("Invalid number.")
            return
        
        recorded_by = input("Recorded by (name): ").strip() or "Staff"
        notes = input("Notes (optional): ").strip()
        
        # Create usage record
        usage_id = f"USE{datetime.now().strftime('%Y%m%d%H%M%S')}"
        usage = DailyUsage(
            id=usage_id,
            item_id=item.id,
            item_name=item.name,
            date=date.today(),
            quantity_used=qty_used,
            recorded_by=recorded_by,
            notes=notes
        )
        
        self.usage_log.append(usage)
        
        # Update item quantity
        item.quantity = max(0, item.quantity - qty_used)
        item.last_updated = datetime.now()
        
        self._save_data()
        print(f"\n✓ Usage recorded: {qty_used} {item.unit} of {item.name}")
        print(f"  Remaining quantity: {item.quantity} {item.unit}")
        
        if item.is_low_stock:
            print(f"\n⚠ Warning: {item.name} is now below minimum quantity!")
