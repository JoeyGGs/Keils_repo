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
        
        # Auto-rotate based on EXIF (phone photos are often rotated)
        try:
            from PIL import ExifTags
            exif = image._getexif()
            if exif:
                for tag, value in exif.items():
                    if ExifTags.TAGS.get(tag) == 'Orientation':
                        if value == 3:
                            image = image.rotate(180, expand=True)
                        elif value == 6:
                            image = image.rotate(270, expand=True)
                        elif value == 8:
                            image = image.rotate(90, expand=True)
                        break
        except Exception:
            pass
        
        # Resize large phone photos — Tesseract works best around 300 DPI
        # Very large images slow it down and can cause worse results
        max_dim = 3000
        w, h = image.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            image = image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast for phone photos
        try:
            from PIL import ImageEnhance, ImageFilter
            # Sharpen twice for blurry phone photos
            image = image.filter(ImageFilter.SHARPEN)
            image = image.filter(ImageFilter.SHARPEN)
            # Boost contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            # Boost sharpness  
            enhancer2 = ImageEnhance.Sharpness(image)
            image = enhancer2.enhance(2.0)
        except Exception:
            pass
        
        # Prepare multiple image variants for OCR
        variants = []
        
        # Variant 1: Adaptive binary threshold
        try:
            import numpy as np
            arr = np.array(image)
            # Use Otsu-like thresholding: mean of all pixels
            threshold = int(arr.mean() * 0.85)
            image_bin = image.point(lambda p: 255 if p > threshold else 0)
            variants.append(image_bin)
        except ImportError:
            # Fallback without numpy
            try:
                pixels = list(image.getdata())
                avg = sum(pixels) / len(pixels) if pixels else 128
                threshold = int(avg * 0.85)
                image_bin = image.point(lambda p: 255 if p > threshold else 0)
                variants.append(image_bin)
            except Exception:
                pass
        
        # Variant 2: Inverted binary (white text on dark background)
        try:
            from PIL import ImageOps
            image_inv = ImageOps.invert(image)
            pixels = list(image_inv.getdata())
            avg = sum(pixels) / len(pixels) if pixels else 128
            threshold = int(avg * 0.85)
            image_inv_bin = image_inv.point(lambda p: 255 if p > threshold else 0)
            variants.append(image_inv_bin)
        except Exception:
            pass
        
        # Variant 3: Original grayscale (no binarization)
        variants.append(image)
        
        # Try multiple PSM modes on all variants
        best_text = ''
        for img in variants:
            for psm in [6, 4, 3, 11]:
                try:
                    custom_config = f'--oem 3 --psm {psm}'
                    text = pytesseract.image_to_string(img, config=custom_config)
                    # Score by how many employee names and time patterns we find
                    text_upper = text.upper()
                    emp_hits = sum(1 for emp in self.known_employees if emp in text_upper)
                    time_hits = len(re.findall(r'\d{1,2}(?::\d{2})?\s*[-–—]\s*\d{1,2}(?::\d{2})?', text))
                    score = emp_hits * 10 + time_hits + len(text.strip())
                    
                    best_score = 0
                    if best_text:
                        bt_upper = best_text.upper()
                        best_emp = sum(1 for emp in self.known_employees if emp in bt_upper)
                        best_time = len(re.findall(r'\d{1,2}(?::\d{2})?\s*[-–—]\s*\d{1,2}(?::\d{2})?', best_text))
                        best_score = best_emp * 10 + best_time + len(best_text.strip())
                    
                    if score > best_score:
                        best_text = text
                except Exception:
                    continue
        
        return best_text
    
    def parse_time(self, time_str: str, is_end_time: bool = False, start_hour: int = None) -> Optional[time]:
        """Parse time string like '5', '9:30', '13:30' into time object.
        Uses context to determine AM/PM for 12-hour format times.
        
        Deli schedule assumptions:
          - Shifts typically run between 5:00 AM and 10:00 PM
          - Start times 5-11 are AM
          - Start time 12 is noon (12:00 PM)
          - End times are determined relative to the start time
          - If end hour < start hour and end < 12, it's PM
        """
        time_str = time_str.strip()
        
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                hour = int(parts[0])
                minute = int(parts[1])
            else:
                hour = int(time_str)
                minute = 0
            
            # Already in 24h format
            if hour >= 13:
                return time(min(hour, 23), minute)
            
            if is_end_time and start_hour is not None:
                # End time logic: if end hour seems too early, add 12
                # e.g. start=5 (AM), end=1 → end=13 (1 PM)
                # e.g. start=9 (AM), end=5 → end=17 (5 PM)
                # e.g. start=12 (noon), end=8 → end=20 (8 PM)
                if hour < start_hour and hour < 12:
                    hour += 12
                elif hour == 12:
                    pass  # 12 is noon
                # If start is PM-range (>=12) and end is small, definitely PM
                elif start_hour >= 12 and hour < 12:
                    hour += 12
            else:
                # Start time logic
                if hour == 12:
                    pass  # 12 is noon
                elif hour < 5:
                    hour += 12  # 1-4 are PM (13-16)
                # 5-11 stay as AM
            
            hour = min(hour, 23)
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
            start_time = self.parse_time(start_str, is_end_time=False)
            
            # Parse end time with context from start time
            start_hour = start_time.hour if start_time else None
            end_time = self.parse_time(end_str, is_end_time=True, start_hour=start_hour)
            
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
        line_upper = line.upper().strip()
        
        # Skip header/day lines
        if any(d in line_upper for d in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']):
            return None
        if line_upper.startswith(('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')):
            return None
        
        # Common OCR character substitutions
        OCR_SUBS = {
            '0': 'O', '1': 'I', '|': 'I', '!': 'I',
            '5': 'S', '8': 'B', '3': 'E', '$': 'S',
            '@': 'A', '(': 'C', '{': 'C',
        }
        
        def clean_ocr(text):
            """Apply common OCR substitution fixes"""
            return ''.join(OCR_SUBS.get(c, c) for c in text)
        
        # Exact match first
        for emp in self.known_employees:
            if emp in line_upper:
                return emp
        
        # Try matching first word with OCR corrections
        words = line_upper.split()
        if not words:
            return None
        first_word = words[0]
        first_word_clean = clean_ocr(first_word)
        
        for emp in self.known_employees:
            if first_word == emp or first_word_clean == emp:
                return emp
        
        # Try first two words joined (OCR sometimes splits names)
        if len(words) >= 2:
            first_two = words[0] + words[1]
            first_two_clean = clean_ocr(first_two)
            for emp in self.known_employees:
                if first_two == emp or first_two_clean == emp:
                    return emp
        
        # Fuzzy matching for OCR errors (allow more tolerance for longer names)
        for emp in self.known_employees:
            tolerance = 1 if len(emp) <= 5 else 2
            
            # Check first word
            if abs(len(first_word) - len(emp)) <= 1:
                matches = sum(1 for a, b in zip(emp, first_word) if a == b)
                if matches >= len(emp) - tolerance:
                    return emp
                # Also try with OCR corrections
                matches_clean = sum(1 for a, b in zip(emp, first_word_clean) if a == b)
                if matches_clean >= len(emp) - tolerance:
                    return emp
            
            # Check anywhere in line (sliding window)
            for i in range(max(0, len(line_upper) - len(emp) + 2)):
                substr = line_upper[i:i+len(emp)]
                if len(substr) >= len(emp) - 1:
                    matches = sum(1 for a, b in zip(emp, substr) if a == b)
                    if matches >= len(emp) - tolerance:
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
            
            # Remove the employee name from line first
            line_without_name = line.upper().replace(employee, '', 1)
            
            # Split line into cells - try multiple strategies
            # Strategy 1: pipe delimiters (common in table OCR)
            if '|' in line_without_name:
                cells = [c.strip() for c in line_without_name.split('|') if c.strip()]
            else:
                # Strategy 2: multiple spaces or tabs
                cells = re.split(r'\s{2,}|\t', line_without_name)
                cells = [c.strip() for c in cells if c.strip()]
            
            # If we got too few cells, try splitting by single space groups
            # where a cell starts with a digit or OFF/R/O
            if len(cells) < 3:
                cell_pattern = re.compile(
                    r'(\d{1,2}(?::\d{2})?\s*[-\u2013\u2014]\s*\d{1,2}(?::\d{2})?(?:\s*[A-Z]{2,4})?|OFF|0FF|R/O|RO|R/0|R0|MEAT|BAR|MID|OP|CK|FR|PM)',
                    re.IGNORECASE
                )
                found = cell_pattern.findall(line_without_name)
                if len(found) >= len(cells):
                    cells = [c.strip() for c in found]
            
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
