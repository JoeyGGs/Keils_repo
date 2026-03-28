"""
Data Models for Keil's Service Deli System
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import Optional, List
from enum import Enum


class StationType(Enum):
    BAR = "BAR"
    MID = "MID"
    OP = "OP"
    CK = "CK"
    FR = "FR"
    MEAT = "MEAT"
    PM = "PM"
    NONE = ""


class ItemCategory(Enum):
    MEATS_CHEESES = "Meats & Cheeses"
    SALADS = "Salads"
    BREADS = "Breads"
    CONDIMENTS = "Condiments"
    SUPPLIES_PLASTICS = "Supplies & Plastics"
    OTHER = "Other"


@dataclass
class Employee:
    id: str
    name: str
    phone: str = ""
    email: str = ""
    position: str = "Deli Associate"
    hire_date: date = field(default_factory=date.today)
    hourly_rate: float = 15.00
    max_hours_per_week: int = 40
    availability: dict = field(default_factory=dict)


@dataclass
class Shift:
    id: str
    employee_id: str
    employee_name: str
    date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    station: str = ""  # BAR, MID, OP, CK, FR, MEAT, PM
    is_off: bool = False  # OFF day
    is_request_off: bool = False  # R/O
    notes: str = ""
    
    @property
    def display_text(self) -> str:
        """Get display text for the shift"""
        if self.is_off:
            return "OFF"
        if self.is_request_off:
            return "R/O"
        if self.start_time and self.end_time:
            start_str = self._format_time(self.start_time)
            end_str = self._format_time(self.end_time)
            station_str = f" {self.station}" if self.station else ""
            return f"{start_str}-{end_str}{station_str}"
        if self.station:
            return self.station
        return ""
    
    def _format_time(self, t: time) -> str:
        """Format time for display (e.g., 5, 9:30, 1:30)"""
        if t.minute == 0:
            hour = t.hour if t.hour <= 12 else t.hour - 12
            if hour == 0:
                hour = 12
            return str(hour)
        else:
            hour = t.hour if t.hour <= 12 else t.hour - 12
            if hour == 0:
                hour = 12
            return f"{hour}:{t.minute:02d}"
    
    @property
    def duration_hours(self) -> float:
        """Calculate shift duration in hours (minus 30 min unpaid break)"""
        if self.is_off or self.is_request_off or not self.start_time or not self.end_time:
            return 0
        
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        
        # Handle overnight shifts
        if end_minutes < start_minutes:
            end_minutes += 24 * 60
        
        total_minutes = end_minutes - start_minutes
        
        # Subtract 30 minute unpaid break for shifts
        if total_minutes > 0:
            total_minutes -= 30
        
        return max(0, total_minutes / 60)


@dataclass
class InventoryItem:
    id: str
    name: str
    category: ItemCategory
    quantity: float
    unit: str  # e.g., "lbs", "each", "gallons"
    min_quantity: float  # Reorder threshold
    cost_per_unit: float = 0.0
    cost_type: str = "unit"  # "unit" or "lbs"
    supplier: str = ""
    last_updated: datetime = field(default_factory=datetime.now)
    notes: str = ""
    
    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_quantity


@dataclass 
class DailyUsage:
    id: str
    item_id: str
    item_name: str
    date: date
    quantity_used: float
    recorded_by: str
    notes: str = ""


@dataclass
class InventoryCountEntry:
    """Single item entry in an inventory count"""
    item_id: str
    item_name: str
    category: str
    expected_quantity: float  # From system
    counted_quantity: float   # Actual count
    unit: str
    difference: float = 0.0   # counted - expected
    notes: str = ""


@dataclass
class InventoryCount:
    """Full inventory count session (done every 6 months)"""
    id: str
    count_date: date
    started_at: datetime
    completed_at: Optional[datetime] = None
    counted_by: str = ""
    status: str = "in_progress"  # in_progress, completed
    entries: List[InventoryCountEntry] = field(default_factory=list)
    notes: str = ""
    
    @property
    def total_items(self) -> int:
        return len(self.entries)
    
    @property
    def items_with_variance(self) -> int:
        return len([e for e in self.entries if e.difference != 0])
    
    @property
    def total_variance_value(self) -> float:
        return sum(e.difference for e in self.entries)
