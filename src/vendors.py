"""
Vendor Management for Keil's Service Deli
"""

from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime
from pathlib import Path
import json


@dataclass
class Vendor:
    id: str
    name: str
    contact_name: str = ""
    phone: str = ""
    email: str = ""
    categories: List[str] = field(default_factory=list)  # Item categories they supply
    notes: str = ""
    

# Default vendors for Keil's Service Deli
DEFAULT_VENDORS = [
    Vendor(
        id="V001",
        name="Boar's Head",
        contact_name="",
        phone="1-800-352-6277",
        email="",
        categories=["MEATS", "CHEESES"],
        notes="Premium deli meats and cheeses"
    ),
    Vendor(
        id="V002",
        name="Sysco",
        contact_name="",
        phone="",
        email="",
        categories=["MEATS", "CHEESES", "CONDIMENTS", "SUPPLIES", "BREADS"],
        notes="General food service distributor"
    ),
    Vendor(
        id="V003",
        name="US Foods",
        contact_name="",
        phone="",
        email="",
        categories=["MEATS", "CHEESES", "SALADS", "CONDIMENTS", "SUPPLIES"],
        notes="Food service distributor"
    ),
    Vendor(
        id="V004",
        name="Local Bakery",
        contact_name="",
        phone="",
        email="",
        categories=["BREADS"],
        notes="Fresh bread delivery"
    ),
    Vendor(
        id="V005",
        name="Restaurant Depot",
        contact_name="",
        phone="",
        email="",
        categories=["SUPPLIES", "CONDIMENTS"],
        notes="Supplies and bulk items"
    ),
]


class VendorManager:
    def __init__(self):
        self.data_file = Path(__file__).parent.parent / "data" / "vendors.json"
        self.vendors = self._load_vendors()
    
    def _load_vendors(self) -> Dict[str, Vendor]:
        """Load vendors from JSON file, or use defaults if file doesn't exist"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {
                        v['id']: Vendor(
                            id=v['id'],
                            name=v['name'],
                            contact_name=v.get('contact_name', ''),
                            phone=v.get('phone', ''),
                            email=v.get('email', ''),
                            categories=v.get('categories', []),
                            notes=v.get('notes', '')
                        )
                        for v in data
                    }
            except (json.JSONDecodeError, IOError):
                pass
        
        # Initialize with defaults and save
        vendors = {v.id: v for v in DEFAULT_VENDORS}
        self._save_vendors(vendors)
        return vendors
    
    def _save_vendors(self, vendors: Dict[str, Vendor] = None):
        """Save vendors to JSON file"""
        if vendors is None:
            vendors = self.vendors
        
        data = [
            {
                'id': v.id,
                'name': v.name,
                'contact_name': v.contact_name,
                'phone': v.phone,
                'email': v.email,
                'categories': v.categories,
                'notes': v.notes
            }
            for v in vendors.values()
        ]
        
        self.data_file.parent.mkdir(exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_all_vendors(self) -> List[Vendor]:
        return list(self.vendors.values())
    
    def get_vendor(self, vendor_id: str) -> Vendor:
        return self.vendors.get(vendor_id)
    
    def get_vendors_by_category(self, category: str) -> List[Vendor]:
        return [v for v in self.vendors.values() if category.upper() in v.categories]
    
    def add_vendor(self, vendor: Vendor):
        self.vendors[vendor.id] = vendor
        self._save_vendors()
    
    def update_vendor(self, vendor_id: str, **kwargs):
        if vendor_id in self.vendors:
            vendor = self.vendors[vendor_id]
            for key, value in kwargs.items():
                if hasattr(vendor, key):
                    setattr(vendor, key, value)
            self._save_vendors()
    
    def delete_vendor(self, vendor_id: str) -> bool:
        if vendor_id in self.vendors:
            del self.vendors[vendor_id]
            self._save_vendors()
            return True
        return False
