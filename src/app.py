"""
Main Application Controller for Keil's Service Deli
"""

from src.schedule import ScheduleManager
from src.inventory import InventoryManager
from src.dashboard import ShiftsDashboard


class DeliApp:
    def __init__(self):
        self.schedule_manager = ScheduleManager()
        self.inventory_manager = InventoryManager()
        self.dashboard = ShiftsDashboard()
        
    def run(self):
        """Main application loop"""
        while True:
            self._display_main_menu()
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                self._schedule_menu()
            elif choice == "2":
                self._inventory_menu()
            elif choice == "3":
                self._dashboard_menu()
            elif choice == "4":
                print("\nThank you for using Keil's Service Deli System. Goodbye!")
                break
            else:
                print("\nInvalid choice. Please try again.")
    
    def _display_main_menu(self):
        print("\n" + "=" * 50)
        print("   KEIL'S SERVICE DELI MANAGEMENT SYSTEM")
        print("=" * 50)
        print("\n1. Schedule Management")
        print("2. Inventory Management")
        print("3. Shifts Dashboard")
        print("4. Exit")
    
    def _schedule_menu(self):
        """Handle schedule management operations"""
        while True:
            print("\n" + "-" * 40)
            print("   SCHEDULE MANAGEMENT")
            print("-" * 40)
            print("\n1. View Weekly Schedule")
            print("2. Add Employee Shift")
            print("3. Remove Employee Shift")
            print("4. View Employee Availability")
            print("5. Generate Weekly Schedule")
            print("6. Back to Main Menu")
            
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == "1":
                self.schedule_manager.view_weekly_schedule()
            elif choice == "2":
                self.schedule_manager.add_shift()
            elif choice == "3":
                self.schedule_manager.remove_shift()
            elif choice == "4":
                self.schedule_manager.view_availability()
            elif choice == "5":
                self.schedule_manager.generate_schedule()
            elif choice == "6":
                break
            else:
                print("\nInvalid choice. Please try again.")
    
    def _inventory_menu(self):
        """Handle inventory management operations"""
        while True:
            print("\n" + "-" * 40)
            print("   INVENTORY MANAGEMENT")
            print("-" * 40)
            print("\n1. View All Inventory")
            print("2. Add New Item")
            print("3. Update Item Quantity")
            print("4. Remove Item")
            print("5. Check Low Stock Items")
            print("6. Record Daily Usage")
            print("7. Back to Main Menu")
            
            choice = input("\nEnter your choice (1-7): ").strip()
            
            if choice == "1":
                self.inventory_manager.view_inventory()
            elif choice == "2":
                self.inventory_manager.add_item()
            elif choice == "3":
                self.inventory_manager.update_quantity()
            elif choice == "4":
                self.inventory_manager.remove_item()
            elif choice == "5":
                self.inventory_manager.check_low_stock()
            elif choice == "6":
                self.inventory_manager.record_usage()
            elif choice == "7":
                break
            else:
                print("\nInvalid choice. Please try again.")
    
    def _dashboard_menu(self):
        """Handle shifts dashboard operations"""
        while True:
            print("\n" + "-" * 40)
            print("   SHIFTS DASHBOARD")
            print("-" * 40)
            print("\n1. Today's Shifts Overview")
            print("2. Current Staff on Duty")
            print("3. Weekly Hours Summary")
            print("4. Upcoming Shifts")
            print("5. Shift Coverage Report")
            print("6. Back to Main Menu")
            
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == "1":
                self.dashboard.todays_overview()
            elif choice == "2":
                self.dashboard.current_staff()
            elif choice == "3":
                self.dashboard.weekly_hours_summary()
            elif choice == "4":
                self.dashboard.upcoming_shifts()
            elif choice == "5":
                self.dashboard.coverage_report()
            elif choice == "6":
                break
            else:
                print("\nInvalid choice. Please try again.")
