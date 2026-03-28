"""
Initialize schedule data for week of 12/22 - 12/28
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, time
from src.data_store import DataStore
from src.models import Employee, Shift

data_store = DataStore()

# Clear existing data
employees = []
shifts = []

# Add all employees
employee_data = [
    ("EMP001", "Michael"),
    ("EMP002", "Steve"),
    ("EMP003", "Lilah"),
    ("EMP004", "Erin"),
    ("EMP005", "Rashid"),
    ("EMP006", "Haley"),
    ("EMP007", "Ellen"),
    ("EMP008", "Mirna"),
    ("EMP009", "Gianni"),
    ("EMP010", "Joey"),
    ("EMP011", "Brandt"),
    ("EMP012", "Richard"),
    ("EMP013", "Simon"),
]

for emp_id, name in employee_data:
    employees.append(Employee(
        id=emp_id,
        name=name,
        position="Deli Associate"
    ))

# Helper function to create shifts
def add_shift(emp_id, emp_name, shift_date, start_h=None, start_m=0, end_h=None, end_m=0, station="", is_off=False, is_ro=False):
    shift_id = f"SH{emp_id}_{shift_date.isoformat()}"
    
    start_time = time(start_h, start_m) if start_h is not None else None
    end_time = time(end_h, end_m) if end_h is not None else None
    
    shifts.append(Shift(
        id=shift_id,
        employee_id=emp_id,
        employee_name=emp_name,
        date=shift_date,
        start_time=start_time,
        end_time=end_time,
        station=station,
        is_off=is_off,
        is_request_off=is_ro
    ))

# Week dates
mon = date(2024, 12, 22)
tue = date(2024, 12, 23)
wed = date(2024, 12, 24)
thu = date(2024, 12, 25)
fri = date(2024, 12, 26)
sat = date(2024, 12, 27)
sun = date(2024, 12, 28)

# Michael - 32 hours
add_shift("EMP001", "Michael", mon, is_off=True)
add_shift("EMP001", "Michael", tue, is_off=True)
add_shift("EMP001", "Michael", wed, is_off=True)
add_shift("EMP001", "Michael", thu, 7, 0, 15, 30, "PM")  # 7-3:30 PM
add_shift("EMP001", "Michael", fri, 9, 30, 18, 0, "MID")  # 9:30-6 MID
add_shift("EMP001", "Michael", sat, 9, 30, 18, 0, "MID")  # 9:30-6 MID
add_shift("EMP001", "Michael", sun, 9, 30, 18, 0, "MID")  # 9:30-6 MID

# Steve - 40 hours
add_shift("EMP002", "Steve", mon, 9, 30, 18, 0, "MID")  # 9:30-6 MID
add_shift("EMP002", "Steve", tue, 9, 30, 18, 0, "MID")  # 9:30-6 MID
add_shift("EMP002", "Steve", wed, 9, 30, 18, 0, "MID")  # 9:30-6 MID
add_shift("EMP002", "Steve", thu, 6, 0, 14, 30, "MID")  # 6-2:30 MID
add_shift("EMP002", "Steve", fri, is_ro=True)
add_shift("EMP002", "Steve", sat, is_ro=True)
add_shift("EMP002", "Steve", sun, 5, 0, 13, 30, "OP")  # 5-1:30 OP

# Lilah - 32 hours
add_shift("EMP003", "Lilah", mon, 5, 0, 13, 30, "BAR")  # 5-1:30 BAR
add_shift("EMP003", "Lilah", wed, 5, 0, 13, 30, "BAR")  # 5-1:30 BAR
add_shift("EMP003", "Lilah", thu, is_ro=True)
add_shift("EMP003", "Lilah", fri, 5, 0, 13, 30, "BAR")  # 5-1:30 BAR
add_shift("EMP003", "Lilah", sun, 5, 0, 13, 30, "BAR")  # 5-1:30 BAR

# Erin - 32 hours
add_shift("EMP004", "Erin", mon, 5, 0, 13, 30, "CK")  # 5-1:30 CK
add_shift("EMP004", "Erin", tue, 5, 0, 13, 30, "BAR")  # 5-1:30 BAR
add_shift("EMP004", "Erin", thu, 5, 0, 13, 30, "OP")  # 5-1:30 OP
add_shift("EMP004", "Erin", fri, 5, 0, 13, 30, "CK")  # 5-1:30 CK

# Rashid - 16 hours
add_shift("EMP005", "Rashid", tue, 12, 0, 20, 30, "PM")  # 12-8:30 PM
add_shift("EMP005", "Rashid", wed, station="MEAT")  # MEAT
add_shift("EMP005", "Rashid", thu, station="MEAT")  # MEAT
add_shift("EMP005", "Rashid", sat, 5, 0, 13, 30, "BAR")  # 5-1:30 BAR

# Haley - 32 hours
add_shift("EMP006", "Haley", mon, 5, 0, 13, 30, "OP")  # 5-1:30 OP
add_shift("EMP006", "Haley", tue, 5, 0, 13, 30, "OP")  # 5-1:30 OP
add_shift("EMP006", "Haley", wed, 5, 0, 13, 30, "OP")  # 5-1:30 OP
add_shift("EMP006", "Haley", thu, is_ro=True)
add_shift("EMP006", "Haley", sat, 5, 0, 13, 30, "OP")  # 5-1:30 OP
add_shift("EMP006", "Haley", sun, is_ro=True)

# Ellen - 40 hours
add_shift("EMP007", "Ellen", mon, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP007", "Ellen", wed, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP007", "Ellen", thu, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP007", "Ellen", fri, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP007", "Ellen", sat, 6, 0, 14, 30, "FR")  # 6-2:30 FR

# Mirna - 40 hours
add_shift("EMP008", "Mirna", mon, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP008", "Mirna", tue, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP008", "Mirna", fri, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP008", "Mirna", sat, 6, 0, 14, 30, "FR")  # 6-2:30 FR
add_shift("EMP008", "Mirna", sun, 6, 0, 14, 30, "FR")  # 6-2:30 FR

# Gianni - 16 hours
add_shift("EMP009", "Gianni", tue, is_ro=True)
add_shift("EMP009", "Gianni", wed, 12, 0, 20, 30, "PM")  # 12-8:30 PM
add_shift("EMP009", "Gianni", fri, 12, 0, 20, 30, "PM")  # 12-8:30 PM

# Joey - 32 hours
add_shift("EMP010", "Joey", mon, is_ro=True)
add_shift("EMP010", "Joey", tue, is_ro=True)
add_shift("EMP010", "Joey", wed, is_ro=True)
add_shift("EMP010", "Joey", thu, 7, 0, 15, 30, "PM")  # 7-3:30 PM
add_shift("EMP010", "Joey", fri, 5, 0, 13, 30, "OP")  # 5-1:30 OP
add_shift("EMP010", "Joey", sat, 12, 0, 20, 30, "PM")  # 12-8:30 PM
add_shift("EMP010", "Joey", sun, 12, 0, 20, 30, "PM")  # 12-8:30 PM

# Brandt - 8 hours
add_shift("EMP011", "Brandt", mon, 12, 0, 20, 30, "PM")  # 12-8:30 PM
add_shift("EMP011", "Brandt", tue, is_ro=True)
add_shift("EMP011", "Brandt", wed, is_ro=True)
add_shift("EMP011", "Brandt", thu, is_ro=True)
add_shift("EMP011", "Brandt", fri, is_ro=True)
add_shift("EMP011", "Brandt", sat, is_ro=True)
add_shift("EMP011", "Brandt", sun, is_ro=True)

# Richard - 24 hours
add_shift("EMP012", "Richard", wed, 13, 0, 21, 30, "PM")  # 1-9:30 PM
add_shift("EMP012", "Richard", thu, is_ro=True)
add_shift("EMP012", "Richard", fri, is_ro=True)
add_shift("EMP012", "Richard", sat, 13, 0, 21, 30, "PM")  # 1-9:30 PM
add_shift("EMP012", "Richard", sun, 13, 0, 21, 30, "PM")  # 1-9:30 PM

# Simon - 24 hours
add_shift("EMP013", "Simon", mon, 13, 0, 21, 30, "PM")  # 1-9:30 PM
add_shift("EMP013", "Simon", tue, 13, 0, 21, 30, "PM")  # 1-9:30 PM
add_shift("EMP013", "Simon", fri, 13, 0, 21, 30, "PM")  # 1-9:30 PM

# Save to database
data_store.save_employees(employees)
data_store.save_shifts(shifts)

print(f"✓ Added {len(employees)} employees")
print(f"✓ Added {len(shifts)} shifts")
print("Schedule for week of 12/22 - 12/28 has been loaded!")
