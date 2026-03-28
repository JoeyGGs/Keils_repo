"""
OCR Schedule Parser for Keil's Service Deli
Parses schedule images and extracts shift data
"""

import re
from datetime import time, date, timedelta
from typing import List, Dict, Optional, Tuple
from PIL import Image
import io

try:
    import pytesseract
    # Try common Windows installation paths for Tesseract
    import os
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe',
    ]
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class ScheduleOCRParser:
    """Parse schedule images using OCR"""
    
    # Known employee names (will be loaded from database)
    known_employees = []
    
    # Shift pattern regex - matches times like "5-1:30", "9:30-6", "12-8:30", etc.
    SHIFT_PATTERN = re.compile(
        r'(\d{1,2}(?::\d{2})?)\s*[-–—]\s*(\d{1,2}(?::\d{2})?)\s*([A-Z]{2,4})?',
        re.IGNORECASE
    )
    
    # Station codes
    STATIONS = ['BAR', 'MID', 'OP', 'CK', 'FR', 'MEAT', 'PM']
    
    # Day patterns
    DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
            'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
    
    def __init__(self, employees: List[str] = None):
        """Initialize parser with known employee names"""
        if employees:
            self.known_employees = [e.upper() for e in employees]
    
    def extract_text(self, image_data: bytes) -> str:
        """Extract text from image using OCR"""
        if not TESSERACT_AVAILABLE:
            raise RuntimeError("Tesseract OCR is not installed. Please install from: https://github.com/UB-Mannheim/tesseract/wiki")
        
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to grayscale for better OCR
        if image.mode != 'L':
            image = image.convert('L')
        
        # Use Tesseract with table-friendly settings
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=custom_config)
        
        return text
    
    def parse_time(self, time_str: str) -> Optional[time]:
        """Parse time string like '5', '9:30', '13:30' into time object"""
        time_str = time_str.strip()
        
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                hour = int(parts[0])
                minute = int(parts[1])
            else:
                hour = int(time_str)
                minute = 0
            
            # Handle 12-hour format assumptions
            # Times 1-4 are likely PM (13:00-16:00)
            # Times 5-11 depend on context (could be AM or PM)
            # Times 12 could be noon
            
            # For deli schedule: 5,6 = AM, 9:30 = AM, 12,1 = PM
            if hour < 5:
                hour += 12  # 1-4 becomes 13-16
            
            if hour > 23:
                hour = hour - 12
                
            return time(hour, minute)
        except (ValueError, IndexError):
            return None
    
    def parse_shift_text(self, text: str) -> Dict:
        """Parse a shift cell text like '5-1:30 BAR' into components"""
        text = text.strip().upper()
        
        # Check for OFF
        if text in ['OFF', '0FF', 'OF']:
            return {'type': 'off'}
        
        # Check for R/O (Request Off)
        if text in ['R/O', 'RO', 'R/0', 'R0']:
            return {'type': 'ro'}
        
        # Check for station only (like "MEAT")
        if text in self.STATIONS:
            return {'type': 'station_only', 'station': text}
        
        # Try to match time pattern
        match = self.SHIFT_PATTERN.search(text)
        if match:
            start_str, end_str, station = match.groups()
            start_time = self.parse_time(start_str)
            end_time = self.parse_time(end_str)
            
            # Adjust end time if it seems wrong (e.g., 1:30 should be 13:30)
            if start_time and end_time:
                if end_time < start_time and end_time.hour < 12:
                    end_time = time(end_time.hour + 12, end_time.minute)
            
            station = station.upper() if station and station.upper() in self.STATIONS else ''
            
            # Also check for station after the time pattern
            if not station:
                for s in self.STATIONS:
                    if s in text:
                        station = s
                        break
            
            return {
                'type': 'regular',
                'start_time': start_time,
                'end_time': end_time,
                'station': station
            }
        
        return {'type': 'empty'}
    
    def find_employee_in_line(self, line: str) -> Optional[str]:
        """Find employee name in a line of text"""
        line_upper = line.upper()
        
        for emp in self.known_employees:
            if emp in line_upper:
                return emp
        
        # Also try fuzzy matching for OCR errors
        for emp in self.known_employees:
            # Simple similarity check
            if len(emp) >= 4:
                for i in range(len(line_upper) - len(emp) + 2):
                    substr = line_upper[i:i+len(emp)]
                    matches = sum(1 for a, b in zip(emp, substr) if a == b)
                    if matches >= len(emp) - 1:  # Allow 1 character difference
                        return emp
        
        return None
    
    def parse_schedule_text(self, text: str, week_start: date) -> List[Dict]:
        """Parse OCR text into shift data"""
        lines = text.split('\n')
        results = []
        
        for line in lines:
            if not line.strip():
                continue
            
            # Find employee name
            employee = self.find_employee_in_line(line)
            if not employee:
                continue
            
            # Split line into cells (try common separators)
            # Remove the employee name from line first
            line_without_name = line.upper().replace(employee, '', 1)
            
            # Split by multiple spaces or tabs
            cells = re.split(r'\s{2,}|\t', line_without_name)
            cells = [c.strip() for c in cells if c.strip()]
            
            # Parse each cell as a potential shift
            for i, cell in enumerate(cells[:7]):  # Max 7 days
                shift_data = self.parse_shift_text(cell)
                if shift_data['type'] != 'empty':
                    shift_date = week_start + timedelta(days=i)
                    results.append({
                        'employee': employee,
                        'date': shift_date,
                        **shift_data
                    })
        
        return results
    
    def process_image(self, image_data: bytes, week_start: date, employees: List[str]) -> Tuple[List[Dict], str]:
        """
        Main method to process an uploaded schedule image
        Returns: (list of parsed shifts, raw OCR text)
        """
        self.known_employees = [e.upper() for e in employees]
        
        # Extract text from image
        raw_text = self.extract_text(image_data)
        
        # Parse the text into shifts
        shifts = self.parse_schedule_text(raw_text, week_start)
        
        return shifts, raw_text


def is_tesseract_available() -> bool:
    """Check if Tesseract OCR is available"""
    if not TESSERACT_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
