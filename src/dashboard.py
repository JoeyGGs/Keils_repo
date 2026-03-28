"""
Shifts Dashboard Module for Keil's Service Deli
"""

from datetime import datetime, date, time, timedelta
from typing import List, Dict
from collections import defaultdict

from src.models import Shift, Employee
from src.data_store import DataStore


class ShiftsDashboard:
    def __init__(self):
        self.data_store = DataStore()
        self._load_data()
    
    def _load_data(self):
        """Load employees and shifts from storage"""
        self.employees = self.data_store.load_employees()
        self.shifts = self.data_store.load_shifts()
    
    def _refresh_data(self):
        """Refresh data from storage"""
        self._load_data()
    
    def todays_overview(self):
        """Display overview of today's shifts"""
        self._refresh_data()
        today = date.today()
        
        print(f"\n{'=' * 60}")
        print(f"   TODAY'S SHIFTS - {today.strftime('%A, %B %d, %Y')}")
        print(f"{'=' * 60}")
        
        today_shifts = [s for s in self.shifts if s.date == today]
        
        if not today_shifts:
            print("\n  No shifts scheduled for today.")
            print("\n  Tip: Use Schedule Management to add shifts.")
            return
        
        # Sort by start time
        today_shifts.sort(key=lambda x: x.start_time)
        
        # Summary stats
        total_hours = sum(s.duration_hours for s in today_shifts)
        unique_staff = len(set(s.employee_id for s in today_shifts))
        
        print(f"\n  📊 Summary:")
        print(f"     Total Shifts: {len(today_shifts)}")
        print(f"     Staff Working: {unique_staff}")
        print(f"     Total Hours: {total_hours:.1f}")
        
        print(f"\n  📅 Shift Schedule:")
        print("-" * 55)
        print(f"  {'Employee':<20} {'Start':<12} {'End':<12} {'Hours':>6}")
        print("-" * 55)
        
        for shift in today_shifts:
            hours = shift.duration_hours
            print(f"  {shift.employee_name:<20} {shift.start_time.strftime('%I:%M %p'):<12} {shift.end_time.strftime('%I:%M %p'):<12} {hours:>6.1f}")
            if shift.notes:
                print(f"     📝 {shift.notes}")
        
        print("-" * 55)
    
    def current_staff(self):
        """Display staff currently on duty"""
        self._refresh_data()
        now = datetime.now()
        current_time = now.time()
        today = now.date()
        
        print(f"\n{'=' * 50}")
        print(f"   CURRENT STAFF ON DUTY")
        print(f"   {now.strftime('%I:%M %p - %A, %B %d')}")
        print(f"{'=' * 50}")
        
        today_shifts = [s for s in self.shifts if s.date == today]
        
        on_duty = []
        upcoming = []
        completed = []
        
        for shift in today_shifts:
            # Handle shifts that cross midnight
            end_time = shift.end_time
            if end_time < shift.start_time:  # Crosses midnight
                if current_time >= shift.start_time or current_time <= end_time:
                    on_duty.append(shift)
                elif current_time < shift.start_time:
                    upcoming.append(shift)
                else:
                    completed.append(shift)
            else:
                if shift.start_time <= current_time <= end_time:
                    on_duty.append(shift)
                elif current_time < shift.start_time:
                    upcoming.append(shift)
                else:
                    completed.append(shift)
        
        # Currently working
        print(f"\n  🟢 ON DUTY ({len(on_duty)}):")
        if on_duty:
            for shift in on_duty:
                time_remaining = self._calculate_time_remaining(shift, now)
                print(f"     • {shift.employee_name} - ends {shift.end_time.strftime('%I:%M %p')} ({time_remaining})")
        else:
            print("     No staff currently on duty")
        
        # Coming up
        print(f"\n  🔵 UPCOMING ({len(upcoming)}):")
        if upcoming:
            upcoming.sort(key=lambda x: x.start_time)
            for shift in upcoming:
                starts_in = self._calculate_starts_in(shift, now)
                print(f"     • {shift.employee_name} - starts {shift.start_time.strftime('%I:%M %p')} ({starts_in})")
        else:
            print("     No more shifts today")
        
        # Completed
        print(f"\n  ⚫ COMPLETED ({len(completed)}):")
        if completed:
            for shift in completed:
                print(f"     • {shift.employee_name} - {shift.start_time.strftime('%I:%M %p')} to {shift.end_time.strftime('%I:%M %p')}")
        else:
            print("     No completed shifts yet")
    
    def _calculate_time_remaining(self, shift: Shift, now: datetime) -> str:
        """Calculate remaining time in shift"""
        end_dt = datetime.combine(shift.date, shift.end_time)
        if shift.end_time < shift.start_time:  # Crosses midnight
            end_dt += timedelta(days=1)
        
        remaining = end_dt - now
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes = remainder // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m remaining"
        return f"{minutes}m remaining"
    
    def _calculate_starts_in(self, shift: Shift, now: datetime) -> str:
        """Calculate time until shift starts"""
        start_dt = datetime.combine(shift.date, shift.start_time)
        until_start = start_dt - now
        
        hours, remainder = divmod(until_start.seconds, 3600)
        minutes = remainder // 60
        
        if hours > 0:
            return f"in {hours}h {minutes}m"
        return f"in {minutes}m"
    
    def weekly_hours_summary(self):
        """Display weekly hours for each employee"""
        self._refresh_data()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        print(f"\n{'=' * 60}")
        print(f"   WEEKLY HOURS SUMMARY")
        print(f"   Week of {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}")
        print(f"{'=' * 60}")
        
        # Calculate hours per employee
        hours_by_employee: Dict[str, Dict] = {}
        
        for shift in self.shifts:
            if week_start <= shift.date <= week_end:
                emp_id = shift.employee_id
                if emp_id not in hours_by_employee:
                    hours_by_employee[emp_id] = {
                        'name': shift.employee_name,
                        'hours': 0,
                        'shifts': 0
                    }
                hours_by_employee[emp_id]['hours'] += shift.duration_hours
                hours_by_employee[emp_id]['shifts'] += 1
        
        if not hours_by_employee:
            print("\n  No shifts scheduled this week.")
            return
        
        print(f"\n  {'Employee':<25} {'Shifts':>8} {'Hours':>10} {'Status':<15}")
        print("-" * 60)
        
        total_hours = 0
        total_shifts = 0
        
        for emp_id, data in sorted(hours_by_employee.items(), key=lambda x: x[1]['hours'], reverse=True):
            # Find employee to get max hours
            emp = next((e for e in self.employees if e.id == emp_id), None)
            max_hours = emp.max_hours_per_week if emp else 40
            
            status = ""
            if data['hours'] >= max_hours:
                status = "⚠ AT MAX"
            elif data['hours'] >= max_hours * 0.9:
                status = "⚡ Near Max"
            else:
                status = "✓ OK"
            
            print(f"  {data['name']:<25} {data['shifts']:>8} {data['hours']:>10.1f} {status:<15}")
            total_hours += data['hours']
            total_shifts += data['shifts']
        
        print("-" * 60)
        print(f"  {'TOTAL':<25} {total_shifts:>8} {total_hours:>10.1f}")
    
    def upcoming_shifts(self):
        """Display shifts for the next 7 days"""
        self._refresh_data()
        today = date.today()
        
        print(f"\n{'=' * 60}")
        print(f"   UPCOMING SHIFTS - NEXT 7 DAYS")
        print(f"{'=' * 60}")
        
        for i in range(7):
            current_date = today + timedelta(days=i)
            day_shifts = [s for s in self.shifts if s.date == current_date]
            
            day_label = "TODAY" if i == 0 else ("TOMORROW" if i == 1 else current_date.strftime("%A"))
            
            print(f"\n  {day_label} - {current_date.strftime('%m/%d/%Y')}")
            print("  " + "-" * 45)
            
            if day_shifts:
                day_shifts.sort(key=lambda x: x.start_time)
                for shift in day_shifts:
                    print(f"    {shift.employee_name}: {shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}")
            else:
                print("    No shifts scheduled")
    
    def coverage_report(self):
        """Show shift coverage analysis"""
        self._refresh_data()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        print(f"\n{'=' * 60}")
        print(f"   SHIFT COVERAGE REPORT")
        print(f"   Week of {week_start.strftime('%B %d, %Y')}")
        print(f"{'=' * 60}")
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        # Define expected shifts per day (adjust as needed)
        expected_shifts = {
            "Monday": 2, "Tuesday": 2, "Wednesday": 2,
            "Thursday": 2, "Friday": 3, "Saturday": 3, "Sunday": 2
        }
        
        print(f"\n  {'Day':<12} {'Scheduled':>10} {'Expected':>10} {'Status':<15}")
        print("-" * 50)
        
        total_scheduled = 0
        total_expected = 0
        gaps = []
        
        for i, day in enumerate(days):
            current_date = week_start + timedelta(days=i)
            day_shifts = [s for s in self.shifts if s.date == current_date]
            scheduled = len(day_shifts)
            expected = expected_shifts[day]
            
            total_scheduled += scheduled
            total_expected += expected
            
            if scheduled >= expected:
                status = "✓ Covered"
            elif scheduled > 0:
                status = f"⚠ Need {expected - scheduled} more"
                gaps.append((day, expected - scheduled))
            else:
                status = "❌ No coverage"
                gaps.append((day, expected))
            
            print(f"  {day:<12} {scheduled:>10} {expected:>10} {status:<15}")
        
        print("-" * 50)
        coverage_pct = (total_scheduled / total_expected * 100) if total_expected > 0 else 0
        print(f"  {'TOTAL':<12} {total_scheduled:>10} {total_expected:>10} {coverage_pct:.0f}% coverage")
        
        if gaps:
            print(f"\n  ⚠ Coverage Gaps:")
            for day, needed in gaps:
                print(f"     • {day}: Need {needed} more shift(s)")
        else:
            print(f"\n  ✓ Full coverage for the week!")
