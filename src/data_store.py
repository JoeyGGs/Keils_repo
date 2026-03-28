"""
Data Storage Module for Keil's Service Deli
Handles saving and loading data to/from JSON files
"""

import json
import os
from datetime import datetime, date, time
from typing import List
from pathlib import Path

from src.models import Employee, Shift, InventoryItem, ItemCategory, DailyUsage, InventoryCount, InventoryCountEntry


class DataStore:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Store data in a 'data' folder in the project directory
            self.data_dir = Path(__file__).parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        # Create data directory if it doesn't exist
        self.data_dir.mkdir(exist_ok=True)
        
        # File paths
        self.employees_file = self.data_dir / "employees.json"
        self.shifts_file = self.data_dir / "shifts.json"
        self.inventory_file = self.data_dir / "inventory.json"
        self.usage_file = self.data_dir / "usage_log.json"
        self.inventory_counts_file = self.data_dir / "inventory_counts.json"
    
    # ========== Employee Operations ==========
    
    def save_employees(self, employees: List[Employee]):
        """Save employees to JSON file"""
        data = []
        for emp in employees:
            emp_dict = {
                'id': emp.id,
                'name': emp.name,
                'phone': emp.phone,
                'email': emp.email,
                'position': emp.position,
                'hire_date': emp.hire_date.isoformat(),
                'hourly_rate': emp.hourly_rate,
                'max_hours_per_week': emp.max_hours_per_week,
                'availability': {
                    day: [s.name for s in shifts]
                    for day, shifts in emp.availability.items()
                } if emp.availability else {}
            }
            data.append(emp_dict)
        
        self._write_json(self.employees_file, data)
    
    def load_employees(self) -> List[Employee]:
        """Load employees from JSON file"""
        data = self._read_json(self.employees_file)
        employees = []
        
        for emp_dict in data:
            availability = {}
            for day, shift_names in emp_dict.get('availability', {}).items():
                availability[day] = [ShiftType[name] for name in shift_names if name in ShiftType.__members__]
            
            emp = Employee(
                id=emp_dict['id'],
                name=emp_dict['name'],
                phone=emp_dict.get('phone', ''),
                email=emp_dict.get('email', ''),
                position=emp_dict.get('position', 'Deli Associate'),
                hire_date=date.fromisoformat(emp_dict.get('hire_date', date.today().isoformat())),
                hourly_rate=emp_dict.get('hourly_rate', 15.00),
                max_hours_per_week=emp_dict.get('max_hours_per_week', 40),
                availability=availability if availability else None
            )
            employees.append(emp)
        
        return employees
    
    # ========== Shift Operations ==========
    
    def save_shifts(self, shifts: List[Shift]):
        """Save shifts to JSON file"""
        data = []
        for shift in shifts:
            shift_dict = {
                'id': shift.id,
                'employee_id': shift.employee_id,
                'employee_name': shift.employee_name,
                'date': shift.date.isoformat(),
                'start_time': shift.start_time.isoformat() if shift.start_time else None,
                'end_time': shift.end_time.isoformat() if shift.end_time else None,
                'station': shift.station,
                'is_off': shift.is_off,
                'is_request_off': shift.is_request_off,
                'notes': shift.notes
            }
            data.append(shift_dict)
        
        self._write_json(self.shifts_file, data)
    
    def load_shifts(self) -> List[Shift]:
        """Load shifts from JSON file"""
        data = self._read_json(self.shifts_file)
        shifts = []
        
        for shift_dict in data:
            shift = Shift(
                id=shift_dict['id'],
                employee_id=shift_dict['employee_id'],
                employee_name=shift_dict['employee_name'],
                date=date.fromisoformat(shift_dict['date']),
                start_time=time.fromisoformat(shift_dict['start_time']) if shift_dict.get('start_time') else None,
                end_time=time.fromisoformat(shift_dict['end_time']) if shift_dict.get('end_time') else None,
                station=shift_dict.get('station', ''),
                is_off=shift_dict.get('is_off', False),
                is_request_off=shift_dict.get('is_request_off', False),
                notes=shift_dict.get('notes', '')
            )
            shifts.append(shift)
        
        return shifts
    
    # ========== Inventory Operations ==========
    
    def save_inventory(self, items: List[InventoryItem]):
        """Save inventory to JSON file"""
        data = []
        for item in items:
            item_dict = {
                'id': item.id,
                'name': item.name,
                'category': item.category.name,
                'quantity': item.quantity,
                'unit': item.unit,
                'min_quantity': item.min_quantity,
                'cost_per_unit': item.cost_per_unit,
                'cost_type': item.cost_type,
                'supplier': item.supplier,
                'last_updated': item.last_updated.isoformat(),
                'notes': item.notes
            }
            data.append(item_dict)
        
        self._write_json(self.inventory_file, data)
    
    def load_inventory(self) -> List[InventoryItem]:
        """Load inventory from JSON file"""
        data = self._read_json(self.inventory_file)
        items = []
        
        for item_dict in data:
            # Handle legacy category names
            category_name = item_dict['category']
            if category_name == 'MEATS':
                category_name = 'MEATS_CHEESES'
            elif category_name == 'CHEESES':
                category_name = 'MEATS_CHEESES'
            elif category_name == 'SUPPLIES':
                category_name = 'SUPPLIES_PLASTICS'
            
            item = InventoryItem(
                id=item_dict['id'],
                name=item_dict['name'],
                category=ItemCategory[category_name],
                quantity=item_dict['quantity'],
                unit=item_dict['unit'],
                min_quantity=item_dict['min_quantity'],
                cost_per_unit=item_dict.get('cost_per_unit', 0.0),
                cost_type=item_dict.get('cost_type', 'unit'),
                supplier=item_dict.get('supplier', ''),
                last_updated=datetime.fromisoformat(item_dict.get('last_updated', datetime.now().isoformat())),
                notes=item_dict.get('notes', '')
            )
            items.append(item)
        
        return items
    
    # ========== Usage Log Operations ==========
    
    def save_usage_log(self, usage_log: List[DailyUsage]):
        """Save usage log to JSON file"""
        data = []
        for usage in usage_log:
            usage_dict = {
                'id': usage.id,
                'item_id': usage.item_id,
                'item_name': usage.item_name,
                'date': usage.date.isoformat(),
                'quantity_used': usage.quantity_used,
                'recorded_by': usage.recorded_by,
                'notes': usage.notes
            }
            data.append(usage_dict)
        
        self._write_json(self.usage_file, data)
    
    def load_usage_log(self) -> List[DailyUsage]:
        """Load usage log from JSON file"""
        data = self._read_json(self.usage_file)
        usage_log = []
        
        for usage_dict in data:
            usage = DailyUsage(
                id=usage_dict['id'],
                item_id=usage_dict['item_id'],
                item_name=usage_dict['item_name'],
                date=date.fromisoformat(usage_dict['date']),
                quantity_used=usage_dict['quantity_used'],
                recorded_by=usage_dict['recorded_by'],
                notes=usage_dict.get('notes', '')
            )
            usage_log.append(usage)
        
        return usage_log
    
    # ========== Inventory Count Operations ==========
    
    def save_inventory_counts(self, counts: List[InventoryCount]):
        """Save inventory counts to JSON file"""
        data = []
        for count in counts:
            entries_data = []
            for entry in count.entries:
                entries_data.append({
                    'item_id': entry.item_id,
                    'item_name': entry.item_name,
                    'category': entry.category,
                    'expected_quantity': entry.expected_quantity,
                    'counted_quantity': entry.counted_quantity,
                    'unit': entry.unit,
                    'difference': entry.difference,
                    'notes': entry.notes
                })
            
            count_dict = {
                'id': count.id,
                'count_date': count.count_date.isoformat(),
                'started_at': count.started_at.isoformat(),
                'completed_at': count.completed_at.isoformat() if count.completed_at else None,
                'counted_by': count.counted_by,
                'status': count.status,
                'entries': entries_data,
                'notes': count.notes
            }
            data.append(count_dict)
        
        self._write_json(self.inventory_counts_file, data)
    
    def load_inventory_counts(self) -> List[InventoryCount]:
        """Load inventory counts from JSON file"""
        data = self._read_json(self.inventory_counts_file)
        counts = []
        
        for count_dict in data:
            entries = []
            for entry_dict in count_dict.get('entries', []):
                entry = InventoryCountEntry(
                    item_id=entry_dict['item_id'],
                    item_name=entry_dict['item_name'],
                    category=entry_dict['category'],
                    expected_quantity=entry_dict['expected_quantity'],
                    counted_quantity=entry_dict['counted_quantity'],
                    unit=entry_dict['unit'],
                    difference=entry_dict.get('difference', 0.0),
                    notes=entry_dict.get('notes', '')
                )
                entries.append(entry)
            
            count = InventoryCount(
                id=count_dict['id'],
                count_date=date.fromisoformat(count_dict['count_date']),
                started_at=datetime.fromisoformat(count_dict['started_at']),
                completed_at=datetime.fromisoformat(count_dict['completed_at']) if count_dict.get('completed_at') else None,
                counted_by=count_dict.get('counted_by', ''),
                status=count_dict.get('status', 'in_progress'),
                entries=entries,
                notes=count_dict.get('notes', '')
            )
            counts.append(count)
        
        return counts
    
    # ========== Helper Methods ==========
    
    def _write_json(self, filepath: Path, data: list):
        """Write data to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _read_json(self, filepath: Path) -> list:
        """Read data from JSON file"""
        if not filepath.exists():
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def backup_data(self):
        """Create backup of all data files"""
        backup_dir = self.data_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for file in [self.employees_file, self.shifts_file, self.inventory_file, self.usage_file]:
            if file.exists():
                backup_path = backup_dir / f"{file.stem}_{timestamp}.json"
                backup_path.write_text(file.read_text(encoding='utf-8'), encoding='utf-8')
        
        return backup_dir
