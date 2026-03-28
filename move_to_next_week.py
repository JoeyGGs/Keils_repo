"""
Move schedule to next week (12/22 - 12/28)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, time, timedelta
from src.data_store import DataStore
from src.models import Shift

data_store = DataStore()

# Load existing shifts
shifts = data_store.load_shifts()

# Current week dates (12/15 - 12/21) - wrong week
old_mon = date(2025, 12, 15)
old_sun = date(2025, 12, 21)

# Next week dates (12/22 - 12/28) - correct week
new_mon = date(2025, 12, 22)

# Find shifts from current week and move them to next week
new_shifts = []
for shift in shifts:
    if old_mon <= shift.date <= old_sun:
        # Calculate which day of week this is (0=Monday)
        day_offset = (shift.date - old_mon).days
        new_date = new_mon + timedelta(days=day_offset)
        
        # Create new shift with updated date
        new_shift = Shift(
            id=f"SH{shift.employee_id}_{new_date.isoformat()}",
            employee_id=shift.employee_id,
            employee_name=shift.employee_name,
            date=new_date,
            start_time=shift.start_time,
            end_time=shift.end_time,
            station=shift.station,
            is_off=shift.is_off,
            is_request_off=shift.is_request_off,
            notes=shift.notes
        )
        new_shifts.append(new_shift)
    elif not (old_mon <= shift.date <= old_sun):
        # Keep shifts from other weeks
        new_shifts.append(shift)

data_store.save_shifts(new_shifts)

# Count shifts for next week
next_week_shifts = [s for s in new_shifts if new_mon <= s.date <= (new_mon + timedelta(days=6))]
print(f"✓ Moved schedule to next week (12/22 - 12/28)")
print(f"✓ {len(next_week_shifts)} shifts now on correct week")
