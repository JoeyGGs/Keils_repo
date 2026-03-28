"""
Schedule Management Module for Keil's Service Deli
"""

from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional
import json
import os

from src.models import Employee, Shift, ShiftType
from src.data_store import DataStore


class ScheduleManager:
    def __init__(self):
        self.data_store = DataStore()
        self._load_data()
    
    def _load_data(self):
        """Load employees and shifts from storage"""
        self.employees = self.data_store.load_employees()
        self.shifts = self.data_store.load_shifts()
    
    def _save_data(self):
        """Save current data to storage"""
        self.data_store.save_employees(self.employees)
        self.data_store.save_shifts(self.shifts)
    
    def view_weekly_schedule(self):
        """Display the schedule for the current week"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday
        
        print(f"\n{'=' * 60}")
        print(f"   WEEKLY SCHEDULE: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")
        print(f"{'=' * 60}")
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for i, day in enumerate(days):
            current_date = week_start + timedelta(days=i)
            day_shifts = [s for s in self.shifts if s.date == current_date]
            
            print(f"\n{day} ({current_date.strftime('%m/%d')}):")
            print("-" * 40)
            
            if day_shifts:
                day_shifts.sort(key=lambda x: x.start_time)
                for shift in day_shifts:
                    print(f"  {shift.employee_name}: {shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}")
                    if shift.notes:
                        print(f"    Note: {shift.notes}")
            else:
                print("  No shifts scheduled")
    
    def add_shift(self):
        """Add a new shift for an employee"""
        print("\n--- Add New Shift ---")
        
        # Show available employees
        if not self.employees:
            print("\nNo employees in system. Please add employees first.")
            self._add_employee_prompt()
            return
        
        print("\nAvailable Employees:")
        for i, emp in enumerate(self.employees, 1):
            print(f"  {i}. {emp.name} ({emp.position})")
        
        try:
            emp_choice = int(input("\nSelect employee number: ")) - 1
            if emp_choice < 0 or emp_choice >= len(self.employees):
                print("Invalid selection.")
                return
            employee = self.employees[emp_choice]
        except ValueError:
            print("Invalid input.")
            return
        
        # Get shift date
        date_str = input("Enter shift date (MM/DD/YYYY) or press Enter for today: ").strip()
        if date_str:
            try:
                shift_date = datetime.strptime(date_str, "%m/%d/%Y").date()
            except ValueError:
                print("Invalid date format.")
                return
        else:
            shift_date = date.today()
        
        # Get shift type
        print("\nShift Types:")
        for i, shift_type in enumerate(ShiftType, 1):
            print(f"  {i}. {shift_type.value}")
        
        try:
            type_choice = int(input("\nSelect shift type: ")) - 1
            shift_type = list(ShiftType)[type_choice]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return
        
        # Set times based on shift type
        time_mapping = {
            ShiftType.MORNING: (time(6, 0), time(14, 0)),
            ShiftType.AFTERNOON: (time(14, 0), time(22, 0)),
            ShiftType.CLOSING: (time(16, 0), time(0, 0)),
            ShiftType.FULL_DAY: (time(8, 0), time(17, 0)) 
        }
        start_time, end_time = time_mapping[shift_type]
        
        # Optional notes
        notes = input("Add notes (optional): ").strip()
        
        # Create shift
        shift_id = f"SH{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_shift = Shift(
            id=shift_id,
            employee_id=employee.id,
            employee_name=employee.name,
            date=shift_date,
            shift_type=shift_type,
            start_time=start_time,
            end_time=end_time,
            notes=notes
        )
        
        self.shifts.append(new_shift)
        self._save_data()
        print(f"\n✓ Shift added for {employee.name} on {shift_date.strftime('%m/%d/%Y')}")
    
    def remove_shift(self):
        """Remove a scheduled shift"""
        print("\n--- Remove Shift ---")
        
        # Get date to view shifts
        date_str = input("Enter date to view shifts (MM/DD/YYYY) or Enter for today: ").strip()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%m/%d/%Y").date()
            except ValueError:
                print("Invalid date format.")
                return
        else:
            target_date = date.today()
        
        # Show shifts for that date
        day_shifts = [s for s in self.shifts if s.date == target_date]
        
        if not day_shifts:
            print(f"\nNo shifts scheduled for {target_date.strftime('%m/%d/%Y')}")
            return
        
        print(f"\nShifts for {target_date.strftime('%m/%d/%Y')}:")
        for i, shift in enumerate(day_shifts, 1):
            print(f"  {i}. {shift.employee_name}: {shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}")
        
        try:
            choice = int(input("\nSelect shift to remove (0 to cancel): "))
            if choice == 0:
                return
            if choice < 1 or choice > len(day_shifts):
                print("Invalid selection.")
                return
            
            shift_to_remove = day_shifts[choice - 1]
            self.shifts.remove(shift_to_remove)
            self._save_data()
            print(f"\n✓ Shift removed for {shift_to_remove.employee_name}")
        except ValueError:
            print("Invalid input.")
    
    def view_availability(self):
        """View employee availability"""
        print("\n--- Employee Availability ---")
        
        if not self.employees:
            print("\nNo employees in system.")
            return
        
        for emp in self.employees:
            print(f"\n{emp.name} ({emp.position}):")
            print(f"  Max hours/week: {emp.max_hours_per_week}")
            print("  Available:")
            for day, shifts in emp.availability.items():
                if shifts:
                    shift_names = [s.name for s in shifts]
                    print(f"    {day}: {', '.join(shift_names)}")
    
    def generate_schedule(self):
        """Auto-generate a weekly schedule based on availability"""
        print("\n--- Generate Weekly Schedule ---")
        
        if not self.employees:
            print("\nNo employees available. Please add employees first.")
            return
        
        # Get week start date
        date_str = input("Enter week start date (Monday, MM/DD/YYYY) or Enter for this week: ").strip()
        if date_str:
            try:
                week_start = datetime.strptime(date_str, "%m/%d/%Y").date()
            except ValueError:
                print("Invalid date format.")
                return
        else:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        
        print(f"\nGenerating schedule for week of {week_start.strftime('%m/%d/%Y')}...")
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        generated_count = 0
        
        # Simple round-robin assignment
        emp_index = 0
        for i, day in enumerate(days):
            current_date = week_start + timedelta(days=i)
            
            # Assign morning and afternoon shifts
            for shift_type in [ShiftType.MORNING, ShiftType.AFTERNOON]:
                employee = self.employees[emp_index % len(self.employees)]
                
                time_mapping = {
                    ShiftType.MORNING: (time(6, 0), time(14, 0)),
                    ShiftType.AFTERNOON: (time(14, 0), time(22, 0)),
                }
                start_time, end_time = time_mapping[shift_type]
                
                shift_id = f"SH{datetime.now().strftime('%Y%m%d%H%M%S')}{generated_count}"
                new_shift = Shift(
                    id=shift_id,
                    employee_id=employee.id,
                    employee_name=employee.name,
                    date=current_date,
                    shift_type=shift_type,
                    start_time=start_time,
                    end_time=end_time
                )
                self.shifts.append(new_shift)
                generated_count += 1
                emp_index += 1
        
        self._save_data()
        print(f"\n✓ Generated {generated_count} shifts for the week")
        print("Review the schedule with 'View Weekly Schedule' option")
    
    def _add_employee_prompt(self):
        """Quick prompt to add an employee"""
        add = input("\nWould you like to add an employee now? (y/n): ").strip().lower()
        if add == 'y':
            self.add_employee()
    
    def add_employee(self):
        """Add a new employee to the system"""
        print("\n--- Add New Employee ---")
        
        name = input("Employee name: ").strip()
        if not name:
            print("Name is required.")
            return
        
        phone = input("Phone number (optional): ").strip()
        email = input("Email (optional): ").strip()
        position = input("Position (default: Deli Associate): ").strip() or "Deli Associate"
        
        try:
            hourly_rate = float(input("Hourly rate (default: 15.00): ").strip() or "15.00")
            max_hours = int(input("Max hours per week (default: 40): ").strip() or "40")
        except ValueError:
            print("Invalid number entered. Using defaults.")
            hourly_rate = 15.00
            max_hours = 40
        
        emp_id = f"EMP{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_employee = Employee(
            id=emp_id,
            name=name,
            phone=phone,
            email=email,
            position=position,
            hourly_rate=hourly_rate,
            max_hours_per_week=max_hours
        )
        
        self.employees.append(new_employee)
        self._save_data()
        print(f"\n✓ Employee '{name}' added successfully")
