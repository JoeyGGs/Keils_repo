"""
Keil's Service Deli Management System
- Schedule Creation
- Internal Inventory
- Shifts Dashboard
"""

import sys
from src.app import DeliApp


def main():
    app = DeliApp()
    app.run()


if __name__ == "__main__":
    main()
