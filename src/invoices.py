"""
Invoice OCR System for Keil's Service Deli
Parses vendor invoices to update item prices and track costs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
import re
import uuid

try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
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


@dataclass
class InvoiceLineItem:
    """A single line item parsed from an invoice"""
    description: str
    quantity: float = 0.0
    unit: str = ""
    unit_price: float = 0.0
    total_price: float = 0.0
    sku: str = ""
    matched_inventory_id: str = ""  # Matched to an existing inventory item
    matched_inventory_name: str = ""


@dataclass
class Invoice:
    """A parsed vendor invoice"""
    id: str
    vendor_name: str
    invoice_number: str = ""
    invoice_date: Optional[datetime] = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    raw_text: str = ""
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    status: str = "pending"  # pending, reviewed, applied
    applied_updates: List[Dict] = field(default_factory=list)
    notes: str = ""
    signed: bool = False  # True = settled (has delivery signature)
    matched_order_id: str = ""  # Matched vendor order ID
    order_discrepancies: List[Dict] = field(default_factory=list)  # Item/qty mismatches vs order

    @property
    def item_count(self) -> int:
        return len(self.line_items)

    @property
    def matched_count(self) -> int:
        return len([i for i in self.line_items if i.matched_inventory_id])


class InvoiceOCRParser:
    """Parse vendor invoices using OCR"""

    # Price patterns: $12.34, 12.34, etc.
    PRICE_PATTERN = re.compile(r'\$?\s*(\d{1,6}[.,]\d{2})')

    # Quantity patterns: 2 CS, 1 EA, 3 LB, 5 BX, etc.
    QTY_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*'
        r'(CS|CA|CASE|CASES|EA|EACH|LB|LBS|BX|BOX|PK|PACK|CT|DZ|GAL|GALLON|ROLL|SLEEVE|SL|BAG|BG)?',
        re.IGNORECASE
    )

    # Common unit normalizations
    UNIT_MAP = {
        'CS': 'case', 'CA': 'case', 'CASE': 'case', 'CASES': 'case',
        'EA': 'each', 'EACH': 'each',
        'LB': 'lbs', 'LBS': 'lbs',
        'BX': 'box', 'BOX': 'box',
        'PK': 'pack', 'PACK': 'pack',
        'CT': 'each', 'DZ': 'dozen',
        'GAL': 'gallon', 'GALLON': 'gallon',
        'ROLL': 'roll', 'SLEEVE': 'sleeve', 'SL': 'sleeve',
        'BAG': 'bag', 'BG': 'bag',
    }

    def extract_text(self, image_data: bytes) -> str:
        """Extract text from invoice image using OCR"""
        if not TESSERACT_AVAILABLE or not PIL_AVAILABLE:
            raise RuntimeError(
                "OCR requires Tesseract and Pillow. "
                "Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki"
            )

        image = Image.open(io.BytesIO(image_data))

        # Preprocess for better OCR on invoices
        if image.mode != 'L':
            image = image.convert('L')

        # Use table-friendly OCR settings
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=custom_config)
        return text

    def parse_invoice_text(self, text: str, vendor_name: str = "") -> Invoice:
        """Parse raw OCR text into an Invoice object"""
        invoice = Invoice(
            id=str(uuid.uuid4())[:8].upper(),
            vendor_name=vendor_name,
            raw_text=text,
        )

        lines = text.split('\n')

        # Try to find invoice number
        for line in lines:
            inv_match = re.search(r'(?:INV(?:OICE)?|BILL)\s*#?\s*:?\s*([A-Z0-9-]+)', line, re.IGNORECASE)
            if inv_match:
                invoice.invoice_number = inv_match.group(1).strip()
                break

        # Try to find invoice date
        for line in lines:
            date_match = re.search(
                r'(?:DATE|DATED?)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                line, re.IGNORECASE
            )
            if date_match:
                try:
                    ds = date_match.group(1)
                    for fmt in ('%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y'):
                        try:
                            invoice.invoice_date = datetime.strptime(ds, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
                break

        # Parse line items — look for lines with prices
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Skip header/footer lines
            skip_keywords = [
                'INVOICE', 'BILL TO', 'SHIP TO', 'SOLD TO', 'REMIT', 'PAGE',
                'SUBTOTAL', 'SUB TOTAL', 'TAX', 'TOTAL', 'AMOUNT DUE',
                'THANK YOU', 'TERMS', 'DUE DATE', 'PO BOX', 'PHONE', 'FAX',
                'DATE', 'CUSTOMER', 'ACCOUNT'
            ]
            line_upper = line.upper()
            if any(kw in line_upper for kw in skip_keywords):
                # But still try to grab subtotal/tax/total
                if 'SUBTOTAL' in line_upper or 'SUB TOTAL' in line_upper:
                    prices = self.PRICE_PATTERN.findall(line)
                    if prices:
                        invoice.subtotal = float(prices[-1].replace(',', '.'))
                elif line_upper.strip().startswith('TAX') or ' TAX ' in line_upper:
                    prices = self.PRICE_PATTERN.findall(line)
                    if prices:
                        invoice.tax = float(prices[-1].replace(',', '.'))
                elif 'TOTAL' in line_upper and 'SUB' not in line_upper:
                    prices = self.PRICE_PATTERN.findall(line)
                    if prices:
                        invoice.total = float(prices[-1].replace(',', '.'))
                continue

            # Look for price(s) in the line
            prices = self.PRICE_PATTERN.findall(line)
            if not prices:
                continue

            # Try to extract quantity
            qty_match = self.QTY_PATTERN.search(line)
            quantity = 0.0
            unit = ""
            if qty_match:
                try:
                    quantity = float(qty_match.group(1))
                except ValueError:
                    quantity = 1.0
                if qty_match.group(2):
                    unit = self.UNIT_MAP.get(qty_match.group(2).upper(), qty_match.group(2).lower())

            # Clean description: remove prices and quantities from line
            description = line
            for p in prices:
                description = description.replace('$' + p, '').replace(p, '')
            if qty_match:
                description = description[:qty_match.start()] + description[qty_match.end():]
            description = re.sub(r'\s{2,}', ' ', description).strip()
            description = description.strip('- |')

            if not description or len(description) < 2:
                continue

            # Last price is usually total, second-to-last is unit price
            total_price = float(prices[-1].replace(',', '.'))
            unit_price = float(prices[-2].replace(',', '.')) if len(prices) >= 2 else total_price

            # If quantity detected and unit_price * qty ≈ total, keep it
            if quantity > 0 and len(prices) >= 2:
                computed = round(unit_price * quantity, 2)
                if abs(computed - total_price) > 0.10:
                    # unit_price might actually be the total, try swapping
                    unit_price = total_price / quantity if quantity else total_price

            item = InvoiceLineItem(
                description=description,
                quantity=quantity if quantity > 0 else 1.0,
                unit=unit or "each",
                unit_price=unit_price,
                total_price=total_price,
            )
            invoice.line_items.append(item)

        # Compute total if not found
        if not invoice.total and invoice.line_items:
            invoice.total = sum(i.total_price for i in invoice.line_items)
        if not invoice.subtotal:
            invoice.subtotal = invoice.total - invoice.tax

        return invoice

    def match_to_inventory(self, invoice: Invoice, inventory_items: list) -> Invoice:
        """Try to match invoice line items to existing inventory items by name similarity"""
        for line_item in invoice.line_items:
            best_match = None
            best_score = 0

            desc_words = set(line_item.description.upper().split())

            for inv_item in inventory_items:
                name_words = set(inv_item.name.upper().split())
                if not name_words:
                    continue

                # Word overlap score
                overlap = len(desc_words & name_words)
                score = overlap / max(len(name_words), 1)

                # Boost if item name is a substring of description or vice versa
                if inv_item.name.upper() in line_item.description.upper():
                    score = max(score, 0.9)
                elif line_item.description.upper() in inv_item.name.upper():
                    score = max(score, 0.7)

                if score > best_score and score >= 0.4:
                    best_score = score
                    best_match = inv_item

            if best_match:
                line_item.matched_inventory_id = best_match.id
                line_item.matched_inventory_name = best_match.name

        return invoice


class InvoiceManager:
    """Manages invoice storage and price updates"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.invoices_file = self.data_dir / "invoices.json"

    def load_invoices(self) -> List[Invoice]:
        if not self.invoices_file.exists():
            return []
        try:
            with open(self.invoices_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                invoices = []
                for d in data:
                    items = [InvoiceLineItem(**i) for i in d.get('line_items', [])]
                    invoices.append(Invoice(
                        id=d['id'],
                        vendor_name=d['vendor_name'],
                        invoice_number=d.get('invoice_number', ''),
                        invoice_date=datetime.fromisoformat(d['invoice_date']) if d.get('invoice_date') else None,
                        uploaded_at=datetime.fromisoformat(d['uploaded_at']),
                        raw_text=d.get('raw_text', ''),
                        line_items=items,
                        subtotal=d.get('subtotal', 0.0),
                        tax=d.get('tax', 0.0),
                        total=d.get('total', 0.0),
                        status=d.get('status', 'pending'),
                        applied_updates=d.get('applied_updates', []),
                        notes=d.get('notes', ''),
                        signed=d.get('signed', False),
                        matched_order_id=d.get('matched_order_id', ''),
                        order_discrepancies=d.get('order_discrepancies', []),
                    ))
                return invoices
        except (json.JSONDecodeError, IOError):
            return []

    def save_invoices(self, invoices: List[Invoice]):
        self.data_dir.mkdir(exist_ok=True)
        data = []
        for inv in invoices:
            data.append({
                'id': inv.id,
                'vendor_name': inv.vendor_name,
                'invoice_number': inv.invoice_number,
                'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else None,
                'uploaded_at': inv.uploaded_at.isoformat(),
                'raw_text': inv.raw_text,
                'line_items': [
                    {
                        'description': i.description,
                        'quantity': i.quantity,
                        'unit': i.unit,
                        'unit_price': i.unit_price,
                        'total_price': i.total_price,
                        'sku': i.sku,
                        'matched_inventory_id': i.matched_inventory_id,
                        'matched_inventory_name': i.matched_inventory_name,
                    }
                    for i in inv.line_items
                ],
                'subtotal': inv.subtotal,
                'tax': inv.tax,
                'total': inv.total,
                'status': inv.status,
                'applied_updates': inv.applied_updates,
                'notes': inv.notes,
                'signed': inv.signed,
                'matched_order_id': inv.matched_order_id,
                'order_discrepancies': inv.order_discrepancies,
            })
        with open(self.invoices_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        invoices = self.load_invoices()
        return next((i for i in invoices if i.id == invoice_id), None)

    def add_invoice(self, invoice: Invoice):
        invoices = self.load_invoices()
        invoices.append(invoice)
        self.save_invoices(invoices)

    def update_invoice(self, invoice: Invoice):
        invoices = self.load_invoices()
        for i, inv in enumerate(invoices):
            if inv.id == invoice.id:
                invoices[i] = invoice
                break
        self.save_invoices(invoices)

    def delete_invoice(self, invoice_id: str):
        invoices = self.load_invoices()
        invoices = [i for i in invoices if i.id != invoice_id]
        self.save_invoices(invoices)
