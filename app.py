"""
Keil's Service Deli - Web Application
Flask-based web interface
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime, date, time, timedelta
import os

from flask import Response
from src.auth import AuthManager
from src.data_store import DataStore
from src.models import Employee, Shift, InventoryItem, ItemCategory, InventoryCount, InventoryCountEntry
from src.vendors import VendorManager
from src.order_sheet import OrderSheetGenerator
from src.ocr_parser import ScheduleOCRParser, is_tesseract_available
from src.kehe import KeHEManager, KeHEProduct
from src.vendor_orders import VendorOrderManager, VendorProduct
from src.invoices import InvoiceManager, InvoiceOCRParser, Invoice, InvoiceLineItem

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24)

# Initialize managers
auth_manager = AuthManager()
data_store = DataStore()
vendor_manager = VendorManager()
kehe_manager = KeHEManager()
vendor_order_manager = VendorOrderManager()
invoice_manager = InvoiceManager()
invoice_parser = InvoiceOCRParser()


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def manager_required(f):
    """Decorator to require manager role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session['user'].get('role') != 'manager':
            flash('Manager access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============ Authentication Routes ============

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        user = auth_manager.authenticate(username, password)
        
        if user:
            session['admin_authenticated'] = True
            return redirect(url_for('select_role'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@app.route('/select-role', methods=['GET', 'POST'])
def select_role():
    if not session.get('admin_authenticated'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        role = request.form.get('role')
        user = auth_manager.select_role(role)
        
        if user:
            session['user'] = user
            session.pop('admin_authenticated', None)
            flash(f'Welcome, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid role selection', 'error')
    
    roles = auth_manager.get_available_roles()
    return render_template('select_role.html', roles=roles)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


# ============ Dashboard Routes ============

@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    shifts = data_store.load_shifts()
    employees = data_store.load_employees()
    inventory = data_store.load_inventory()
    
    # Today's shifts (only actual working shifts, not OFF/R/O)
    today_shifts = [s for s in shifts if s.date == today and not s.is_off and not s.is_request_off and s.start_time]
    today_shifts.sort(key=lambda x: x.start_time if x.start_time else time(0, 0))
    
    # Current time for on-duty calculation
    now = datetime.now()
    current_time = now.time()
    
    on_duty = []
    for shift in today_shifts:
        if shift.start_time and shift.end_time:
            if shift.start_time <= current_time <= shift.end_time:
                on_duty.append(shift)
    
    # Low stock items
    low_stock = [i for i in inventory if i.is_low_stock]
    
    # Weekly hours
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_shifts = [s for s in shifts if week_start <= s.date <= week_end]
    total_hours = sum(s.duration_hours for s in week_shifts)
    
    return render_template('dashboard.html',
                         today=today,
                         today_shifts=today_shifts,
                         on_duty=on_duty,
                         low_stock=low_stock,
                         total_employees=len(employees),
                         total_hours=total_hours,
                         current_time=now)


# ============ Schedule Routes ============

@app.route('/schedule')
@login_required
def schedule():
    today = date.today()
    week_offset = int(request.args.get('week', 0))
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)
    
    shifts = data_store.load_shifts()
    employees = data_store.load_employees()
    
    # Build days structure
    days = []
    for i in range(7):
        current_date = week_start + timedelta(days=i)
        day_shifts = [s for s in shifts if s.date == current_date]
        day_total = sum(s.duration_hours for s in day_shifts)
        days.append({
            'date': current_date,
            'name': current_date.strftime('%A'),
            'shifts': day_shifts,
            'total_hours': day_total
        })
    
    # Build schedule data for grid view (employee rows)
    schedule_data = []
    for emp in employees:
        emp_shifts = []
        emp_total = 0
        
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            # Find shift for this employee on this day
            shift = next((s for s in shifts if s.employee_id == emp.id and s.date == current_date), None)
            
            if shift:
                emp_shifts.append({
                    'date': current_date.isoformat(),
                    'display': shift.display_text,
                    'shift_id': shift.id,
                    'is_today': current_date == today
                })
                emp_total += shift.duration_hours
            else:
                emp_shifts.append({
                    'date': current_date.isoformat(),
                    'display': '',
                    'shift_id': '',
                    'is_today': current_date == today
                })
        
        schedule_data.append({
            'id': emp.id,
            'name': emp.name,
            'shifts': emp_shifts,
            'total_hours': emp_total
        })
    
    grand_total = sum(e['total_hours'] for e in schedule_data)
    
    return render_template('schedule.html',
                         days=days,
                         week_start=week_start,
                         week_end=week_end,
                         week_offset=week_offset,
                         employees=employees,
                         schedule_data=schedule_data,
                         grand_total=grand_total,
                         today=today)


@app.route('/schedule/print')
@login_required
def schedule_print():
    today = date.today()
    week_offset = int(request.args.get('week', 0))
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)
    
    shifts = data_store.load_shifts()
    employees = data_store.load_employees()
    
    # Build days structure
    days = []
    for i in range(7):
        current_date = week_start + timedelta(days=i)
        day_shifts = [s for s in shifts if s.date == current_date]
        day_total = sum(s.duration_hours for s in day_shifts)
        days.append({
            'date': current_date,
            'name': current_date.strftime('%A'),
            'total_hours': day_total
        })
    
    # Build schedule data for grid view
    schedule_data = []
    for emp in employees:
        emp_shifts = []
        emp_total = 0
        
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            shift = next((s for s in shifts if s.employee_id == emp.id and s.date == current_date), None)
            
            if shift:
                emp_shifts.append({
                    'date': current_date.isoformat(),
                    'display': shift.display_text
                })
                emp_total += shift.duration_hours
            else:
                emp_shifts.append({
                    'date': current_date.isoformat(),
                    'display': ''
                })
        
        schedule_data.append({
            'name': emp.name,
            'shifts': emp_shifts,
            'total_hours': emp_total
        })
    
    grand_total = sum(e['total_hours'] for e in schedule_data)
    
    return render_template('schedule_print.html',
                         days=days,
                         week_start=week_start,
                         week_end=week_end,
                         schedule_data=schedule_data,
                         grand_total=grand_total)


@app.route('/schedule/update', methods=['POST'])
@login_required
def update_shift():
    employee_id = request.form.get('employee_id')
    employee_name = request.form.get('employee_name')
    shift_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    shift_type = request.form.get('shift_type')
    old_shift_id = request.form.get('old_shift_id')
    week_offset = request.form.get('week_offset', 0)
    
    # Preset shift times
    SHIFT_PRESETS = {
        'opening': (time(5, 0), time(13, 30), 'BAR'),
        'mid': (time(9, 30), time(18, 0), 'MID'),
        'pm': (time(12, 0), time(20, 30), 'PM'),
        'closing': (time(13, 0), time(21, 30), '')
    }
    
    shifts = data_store.load_shifts()
    
    # Remove old shift if exists
    if old_shift_id:
        shifts = [s for s in shifts if s.id != old_shift_id]
    
    # Create new shift based on type
    if shift_type == 'clear' or shift_type == 'preset':
        # Just remove, don't add new
        pass
    elif shift_type == 'off':
        shift_id = f"SH{employee_id}_{shift_date.isoformat()}"
        new_shift = Shift(
            id=shift_id,
            employee_id=employee_id,
            employee_name=employee_name,
            date=shift_date,
            is_off=True
        )
        shifts.append(new_shift)
    elif shift_type == 'ro':
        shift_id = f"SH{employee_id}_{shift_date.isoformat()}"
        new_shift = Shift(
            id=shift_id,
            employee_id=employee_id,
            employee_name=employee_name,
            date=shift_date,
            is_request_off=True
        )
        shifts.append(new_shift)
    elif shift_type in SHIFT_PRESETS:
        # Handle preset shifts (opening, mid, pm, closing)
        start_time, end_time, default_station = SHIFT_PRESETS[shift_type]
        station = request.form.get('station', default_station)
        
        shift_id = f"SH{employee_id}_{shift_date.isoformat()}"
        new_shift = Shift(
            id=shift_id,
            employee_id=employee_id,
            employee_name=employee_name,
            date=shift_date,
            start_time=start_time,
            end_time=end_time,
            station=station
        )
        shifts.append(new_shift)
    elif shift_type == 'custom':
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        station = request.form.get('station', '')
        
        if start_str and end_str:
            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()
            
            shift_id = f"SH{employee_id}_{shift_date.isoformat()}"
            new_shift = Shift(
                id=shift_id,
                employee_id=employee_id,
                employee_name=employee_name,
                date=shift_date,
                start_time=start_time,
                end_time=end_time,
                station=station
            )
            shifts.append(new_shift)
    elif shift_type == 'custom_text':
        custom_text = request.form.get('custom_text', '').strip()
        if custom_text:
            shift_id = f"SH{employee_id}_{shift_date.isoformat()}"
            new_shift = Shift(
                id=shift_id,
                employee_id=employee_id,
                employee_name=employee_name,
                date=shift_date,
                custom_text=custom_text
            )
            shifts.append(new_shift)
    
    data_store.save_shifts(shifts)
    flash('Schedule updated', 'success')
    return redirect(url_for('schedule', week=week_offset))


@app.route('/schedule/create', methods=['POST'])
@login_required
def create_new_schedule():
    """Create next week's schedule from saved presets"""
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    # Target = next week from whichever week the user is currently viewing
    view_offset = int(request.form.get('week_offset', 0))
    next_week_start = current_week_start + timedelta(weeks=view_offset + 1)

    presets = data_store.load_shift_presets()
    if not presets:
        flash('No presets saved yet â€” set up presets first', 'error')
        return redirect(url_for('schedule', week=view_offset))

    employees = data_store.load_employees()
    shifts = data_store.load_shifts()

    SHIFT_PRESETS = {
        'opening': (time(5, 0), time(13, 30), 'BAR'),
        'mid': (time(9, 30), time(18, 0), 'MID'),
        'pm': (time(12, 0), time(20, 30), 'PM'),
        'closing': (time(13, 0), time(21, 30), ''),
    }

    applied = 0
    for emp in employees:
        emp_presets = presets.get(emp.id)
        if not emp_presets:
            continue

        for day_str, preset_info in emp_presets.items():
            day_index = int(day_str)
            shift_date = next_week_start + timedelta(days=day_index)
            shift_type = preset_info.get('shift_type', '')
            station = preset_info.get('station', '')

            if not shift_type:
                continue

            # Remove existing shift for this employee on this date
            shifts = [s for s in shifts if not (s.employee_id == emp.id and s.date == shift_date)]

            shift_id = f"SH{emp.id}_{shift_date.isoformat()}"

            if shift_type == 'off':
                new_shift = Shift(id=shift_id, employee_id=emp.id, employee_name=emp.name, date=shift_date, is_off=True)
            elif shift_type == 'ro':
                new_shift = Shift(id=shift_id, employee_id=emp.id, employee_name=emp.name, date=shift_date, is_request_off=True)
            elif shift_type in SHIFT_PRESETS:
                start_t, end_t, default_station = SHIFT_PRESETS[shift_type]
                new_shift = Shift(id=shift_id, employee_id=emp.id, employee_name=emp.name, date=shift_date,
                                  start_time=start_t, end_time=end_t, station=station or default_station)
            else:
                continue

            shifts.append(new_shift)
            applied += 1

    data_store.save_shifts(shifts)
    next_week_offset = view_offset + 1
    flash(f'Created schedule for week of {next_week_start.strftime("%m/%d/%Y")} ({applied} shifts from presets)', 'success')
    return redirect(url_for('schedule', week=next_week_offset))


@app.route('/schedule/delete/<shift_id>', methods=['POST'])
@login_required
def delete_shift(shift_id):
    shifts = data_store.load_shifts()
    shifts = [s for s in shifts if s.id != shift_id]
    data_store.save_shifts(shifts)
    flash('Shift removed', 'success')
    return redirect(url_for('schedule'))


@app.route('/schedule/delete-week', methods=['POST'])
@login_required
def delete_current_schedule():
    """Delete all shifts for the currently viewed week"""
    week_offset = int(request.form.get('week_offset', 0))
    today = date.today()
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    shifts = data_store.load_shifts()
    before = len(shifts)
    shifts = [s for s in shifts if not (week_start <= s.date <= week_end)]
    removed = before - len(shifts)
    data_store.save_shifts(shifts)

    flash(f'Deleted {removed} shift(s) for week of {week_start.strftime("%m/%d/%Y")}', 'success')
    return redirect(url_for('schedule', week=week_offset))


@app.route('/schedule/presets', methods=['GET'])
@login_required
def get_shift_presets():
    """Return shift presets as JSON"""
    presets = data_store.load_shift_presets()
    return jsonify(presets)


@app.route('/schedule/presets/save', methods=['POST'])
@login_required
def save_shift_presets():
    """Save shift presets for employees"""
    presets_data = request.get_json()
    if presets_data is None:
        return jsonify({'error': 'Invalid data'}), 400
    data_store.save_shift_presets(presets_data)
    return jsonify({'success': True})


@app.route('/schedule/presets/apply', methods=['POST'])
@login_required
def apply_shift_presets():
    """Apply saved presets to the current week's schedule"""
    week_offset = int(request.form.get('week_offset', 0))
    today = date.today()
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)

    presets = data_store.load_shift_presets()
    if not presets:
        flash('No presets saved yet', 'error')
        return redirect(url_for('schedule', week=week_offset))

    employees = data_store.load_employees()
    shifts = data_store.load_shifts()

    SHIFT_PRESETS = {
        'opening': (time(5, 0), time(13, 30), 'BAR'),
        'mid': (time(9, 30), time(18, 0), 'MID'),
        'pm': (time(12, 0), time(20, 30), 'PM'),
        'closing': (time(13, 0), time(21, 30), ''),
    }

    applied = 0
    for emp in employees:
        emp_presets = presets.get(emp.id)
        if not emp_presets:
            continue

        for day_str, preset_info in emp_presets.items():
            day_index = int(day_str)
            shift_date = week_start + timedelta(days=day_index)
            shift_type = preset_info.get('shift_type', '')
            station = preset_info.get('station', '')

            if not shift_type:
                continue

            # Remove existing shift for this employee on this date
            shifts = [s for s in shifts if not (s.employee_id == emp.id and s.date == shift_date)]

            shift_id = f"SH{emp.id}_{shift_date.isoformat()}"

            if shift_type == 'off':
                new_shift = Shift(id=shift_id, employee_id=emp.id, employee_name=emp.name, date=shift_date, is_off=True)
            elif shift_type == 'ro':
                new_shift = Shift(id=shift_id, employee_id=emp.id, employee_name=emp.name, date=shift_date, is_request_off=True)
            elif shift_type in SHIFT_PRESETS:
                start_t, end_t, default_station = SHIFT_PRESETS[shift_type]
                new_shift = Shift(id=shift_id, employee_id=emp.id, employee_name=emp.name, date=shift_date,
                                  start_time=start_t, end_time=end_t, station=station or default_station)
            else:
                continue

            shifts.append(new_shift)
            applied += 1

    data_store.save_shifts(shifts)
    flash(f'Applied {applied} preset shift(s) to week of {week_start.strftime("%m/%d/%Y")}', 'success')
    return redirect(url_for('schedule', week=week_offset))


@app.route('/schedule/ocr', methods=['POST'])
@login_required
def schedule_ocr():
    """Process uploaded schedule image with OCR"""
    if 'schedule_image' not in request.files:
        flash('No image uploaded', 'error')
        return redirect(url_for('schedule'))
    
    file = request.files['schedule_image']
    if file.filename == '':
        flash('No image selected', 'error')
        return redirect(url_for('schedule'))
    
    # Check if Tesseract is available
    if not is_tesseract_available():
        flash('OCR requires Tesseract. Please install from: https://github.com/UB-Mannheim/tesseract/wiki', 'error')
        return redirect(url_for('schedule'))
    
    try:
        # Get week start from form
        week_offset = int(request.form.get('week_offset', 0))
        today = date.today()
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        
        # Get employee names
        employees = data_store.load_employees()
        employee_names = [e.name for e in employees]
        employee_map = {e.name.upper(): e for e in employees}
        
        # Process image
        image_data = file.read()
        parser = ScheduleOCRParser()
        parsed_shifts, raw_text = parser.process_image(image_data, week_start, employee_names)
        
        if not parsed_shifts:
            flash(f'Could not parse any shifts from image. Raw text: {raw_text[:500]}...', 'warning')
            return redirect(url_for('schedule', week=week_offset))
        
        # Load existing shifts and remove current week's shifts
        shifts = data_store.load_shifts()
        week_end = week_start + timedelta(days=6)
        shifts = [s for s in shifts if not (week_start <= s.date <= week_end)]
        
        # Add parsed shifts
        added_count = 0
        for parsed in parsed_shifts:
            emp_name = parsed['employee']
            if emp_name not in employee_map:
                continue
            
            emp = employee_map[emp_name]
            shift_date = parsed['date']
            shift_id = f"SH{emp.id}_{shift_date.isoformat()}"
            
            if parsed['type'] == 'off':
                new_shift = Shift(
                    id=shift_id,
                    employee_id=emp.id,
                    employee_name=emp.name,
                    date=shift_date,
                    is_off=True
                )
            elif parsed['type'] == 'ro':
                new_shift = Shift(
                    id=shift_id,
                    employee_id=emp.id,
                    employee_name=emp.name,
                    date=shift_date,
                    is_request_off=True
                )
            elif parsed['type'] == 'station_only':
                new_shift = Shift(
                    id=shift_id,
                    employee_id=emp.id,
                    employee_name=emp.name,
                    date=shift_date,
                    station=parsed.get('station', '')
                )
            elif parsed['type'] == 'regular':
                new_shift = Shift(
                    id=shift_id,
                    employee_id=emp.id,
                    employee_name=emp.name,
                    date=shift_date,
                    start_time=parsed.get('start_time'),
                    end_time=parsed.get('end_time'),
                    station=parsed.get('station', '')
                )
            else:
                continue
            
            shifts.append(new_shift)
            added_count += 1
        
        data_store.save_shifts(shifts)
        flash(f'OCR imported {added_count} shifts for week of {week_start.strftime("%m/%d")}', 'success')
        
    except Exception as e:
        flash(f'OCR Error: {str(e)}', 'error')
    
    return redirect(url_for('schedule', week=week_offset))


@app.route('/schedule/ocr/check')
@login_required
def check_ocr():
    """Check if OCR is available"""
    return jsonify({'available': is_tesseract_available()})


# ============ Employee Routes ============

@app.route('/employees')
@login_required
def employees():
    employee_list = data_store.load_employees()
    return render_template('employees.html', employees=employee_list)


@app.route('/employees/add', methods=['POST'])
@manager_required
def add_employee():
    name = request.form.get('name')
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    position = request.form.get('position', 'Deli Associate')
    hourly_rate = float(request.form.get('hourly_rate', 15.00))
    max_hours = int(request.form.get('max_hours', 40))
    
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
    
    employees = data_store.load_employees()
    employees.append(new_employee)
    data_store.save_employees(employees)
    
    flash(f'Employee {name} added', 'success')
    return redirect(url_for('employees'))


@app.route('/employees/delete/<emp_id>', methods=['POST'])
@manager_required
def delete_employee(emp_id):
    employees = data_store.load_employees()
    employees = [e for e in employees if e.id != emp_id]
    data_store.save_employees(employees)
    flash('Employee removed', 'success')
    return redirect(url_for('employees'))


@app.route('/employees/update/<emp_id>', methods=['POST'])
@manager_required
def update_employee(emp_id):
    employees = data_store.load_employees()
    
    for emp in employees:
        if emp.id == emp_id:
            old_name = emp.name
            if 'name' in request.form:
                emp.name = request.form.get('name', emp.name)
            if 'position' in request.form:
                emp.position = request.form.get('position', emp.position)
            if 'phone' in request.form:
                emp.phone = request.form.get('phone', '')
            if 'email' in request.form:
                emp.email = request.form.get('email', '')
            if 'max_hours' in request.form:
                emp.max_hours_per_week = int(request.form.get('max_hours', emp.max_hours_per_week))
            
            # Update name in existing shifts if changed
            if emp.name != old_name:
                shifts = data_store.load_shifts()
                for s in shifts:
                    if s.employee_id == emp_id:
                        s.employee_name = emp.name
                data_store.save_shifts(shifts)
            break
    
    data_store.save_employees(employees)
    flash('Employee updated', 'success')
    return redirect(url_for('employees'))


# ============ Inventory Routes ============

@app.route('/orders-inventory')
@login_required
def orders_inventory():
    """Combined Orders & Inventory page"""
    items = data_store.load_inventory()
    vendors = vendor_manager.get_all_vendors()
    
    # Group by category
    by_category = {}
    for item in items:
        cat = item.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    
    low_stock_count = len([i for i in items if i.is_low_stock])
    
    # Generate order data
    generator = OrderSheetGenerator(items)
    low_stock = generator.get_items_to_order()
    
    # Generate order summary for each vendor
    vendor_orders = []
    for vendor in vendors:
        order = generator.generate_order_by_vendor(vendor.id)
        if order:
            vendor_orders.append(order)
    
    # Load inventory counts
    inventory_counts = data_store.load_inventory_counts()
    current_count = next((c for c in inventory_counts if c.status == 'in_progress'), None)
    completed_counts = sorted([c for c in inventory_counts if c.status == 'completed'], 
                              key=lambda x: x.completed_at, reverse=True)
    last_count = completed_counts[0] if completed_counts else None
    
    # Calculate next due date (6 months from last count)
    next_count_due = None
    if last_count:
        from dateutil.relativedelta import relativedelta
        next_count_due = last_count.count_date + relativedelta(months=6)
    
    # Load ordering vendors for the Ordering tab
    ordering_vendors = vendor_manager.get_ordering_vendors()
    
    return render_template('orders_inventory.html',
                         items=items,
                         by_category=by_category,
                         categories=list(ItemCategory),
                         low_stock_count=low_stock_count,
                         vendors=vendors,
                         vendor_orders=vendor_orders,
                         low_stock=low_stock,
                         current_count=current_count,
                         completed_counts=completed_counts,
                         last_count=last_count,
                         next_count_due=next_count_due,
                         ordering_vendors=ordering_vendors,
                         today=date.today())


@app.route('/inventory')
@login_required
def inventory():
    """Redirect old inventory URL to new combined page"""
    return redirect(url_for('orders_inventory'))


@app.route('/inventory/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    category = ItemCategory[request.form.get('category')]
    quantity = float(request.form.get('quantity', 0))
    unit = request.form.get('unit', 'each')
    min_quantity = float(request.form.get('min_quantity', 5))
    cost = float(request.form.get('cost', 0))
    cost_type = request.form.get('cost_type', 'unit')
    supplier = request.form.get('supplier', '')
    
    item_id = f"INV{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_item = InventoryItem(
        id=item_id,
        name=name,
        category=category,
        quantity=quantity,
        unit=unit,
        min_quantity=min_quantity,
        cost_per_unit=cost,
        cost_type=cost_type,
        supplier=supplier
    )
    
    items = data_store.load_inventory()
    items.append(new_item)
    data_store.save_inventory(items)
    
    flash(f'{name} added to inventory', 'success')
    return redirect(url_for('orders_inventory'))


@app.route('/inventory/update/<item_id>', methods=['POST'])
@login_required
def update_inventory(item_id):
    items = data_store.load_inventory()
    
    for item in items:
        if item.id == item_id:
            action = request.form.get('action')
            amount = float(request.form.get('amount', 0))
            
            if action == 'set':
                item.quantity = amount
            elif action == 'add':
                item.quantity += amount
            elif action == 'subtract':
                item.quantity = max(0, item.quantity - amount)
            
            item.last_updated = datetime.now()
            break
    
    data_store.save_inventory(items)
    flash('Inventory updated', 'success')
    return redirect(url_for('orders_inventory'))


@app.route('/inventory/vendor/<item_id>', methods=['POST'])
@login_required
def update_item_vendor(item_id):
    """Update the vendor/supplier for an inventory item"""
    items = data_store.load_inventory()
    
    for item in items:
        if item.id == item_id:
            item.supplier = request.form.get('supplier', '')
            item.last_updated = datetime.now()
            break
    
    data_store.save_inventory(items)
    flash('Supplier updated', 'success')
    return redirect(url_for('orders_inventory'))


@app.route('/inventory/delete/<item_id>', methods=['POST'])
@manager_required
def delete_inventory(item_id):
    items = data_store.load_inventory()
    items = [i for i in items if i.id != item_id]
    data_store.save_inventory(items)
    flash('Item removed', 'success')
    return redirect(url_for('orders_inventory'))


# ============ Inventory Count Routes ============

@app.route('/inventory/count/start', methods=['POST'])
@login_required
def start_inventory_count():
    """Start a new inventory count session"""
    items = data_store.load_inventory()
    counts = data_store.load_inventory_counts()
    
    # Check if there's already an in-progress count
    in_progress = [c for c in counts if c.status == 'in_progress']
    if in_progress:
        flash('There is already an inventory count in progress', 'warning')
        return redirect(url_for('orders_inventory'))
    
    # Create entries for all inventory items
    entries = []
    for item in items:
        entry = InventoryCountEntry(
            item_id=item.id,
            item_name=item.name,
            category=item.category.value,
            expected_quantity=item.quantity,
            counted_quantity=0,
            unit=item.unit,
            difference=0,
            notes=""
        )
        entries.append(entry)
    
    # Create new count
    count_id = f"COUNT{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_count = InventoryCount(
        id=count_id,
        count_date=date.today(),
        started_at=datetime.now(),
        counted_by=session['user']['name'],
        status='in_progress',
        entries=entries,
        notes=""
    )
    
    counts.append(new_count)
    data_store.save_inventory_counts(counts)
    
    flash('Inventory count started', 'success')
    return redirect(url_for('orders_inventory'))


@app.route('/inventory/count/<count_id>')
@login_required
def view_inventory_count(count_id):
    """View a specific inventory count"""
    counts = data_store.load_inventory_counts()
    count = next((c for c in counts if c.id == count_id), None)
    
    if not count:
        flash('Count not found', 'error')
        return redirect(url_for('orders_inventory'))
    
    # Group entries by category
    by_category = {}
    for entry in count.entries:
        cat = entry.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)
    
    return render_template('inventory_count.html', count=count, by_category=by_category)


@app.route('/inventory/count/<count_id>/update', methods=['POST'])
@login_required
def update_inventory_count(count_id):
    """Update counted quantities for an inventory count"""
    counts = data_store.load_inventory_counts()
    count = next((c for c in counts if c.id == count_id), None)
    
    if not count:
        flash('Count not found', 'error')
        return redirect(url_for('orders_inventory'))
    
    if count.status != 'in_progress':
        flash('This count has already been completed', 'warning')
        return redirect(url_for('orders_inventory'))
    
    # Update each entry's counted quantity
    for entry in count.entries:
        field_name = f"qty_{entry.item_id}"
        if field_name in request.form:
            try:
                counted = float(request.form.get(field_name, 0))
                entry.counted_quantity = counted
                entry.difference = counted - entry.expected_quantity
            except ValueError:
                pass
        
        notes_field = f"notes_{entry.item_id}"
        if notes_field in request.form:
            entry.notes = request.form.get(notes_field, '')
    
    data_store.save_inventory_counts(counts)
    flash('Count updated', 'success')
    return redirect(url_for('view_inventory_count', count_id=count_id))


@app.route('/inventory/count/<count_id>/complete', methods=['POST'])
@login_required
def complete_inventory_count(count_id):
    """Complete an inventory count and optionally update inventory quantities"""
    counts = data_store.load_inventory_counts()
    count = next((c for c in counts if c.id == count_id), None)
    
    if not count:
        flash('Count not found', 'error')
        return redirect(url_for('orders_inventory'))
    
    if count.status != 'in_progress':
        flash('This count has already been completed', 'warning')
        return redirect(url_for('orders_inventory'))
    
    # Check if user wants to apply the counted quantities to inventory
    apply_to_inventory = request.form.get('apply_to_inventory') == 'yes'
    
    if apply_to_inventory:
        items = data_store.load_inventory()
        for entry in count.entries:
            for item in items:
                if item.id == entry.item_id:
                    item.quantity = entry.counted_quantity
                    item.last_updated = datetime.now()
                    break
        data_store.save_inventory(items)
    
    # Mark count as completed
    count.status = 'completed'
    count.completed_at = datetime.now()
    count.notes = request.form.get('notes', '')
    
    data_store.save_inventory_counts(counts)
    flash('Inventory count completed' + (' and inventory updated' if apply_to_inventory else ''), 'success')
    return redirect(url_for('orders_inventory'))


@app.route('/inventory/count/<count_id>/delete', methods=['POST'])
@manager_required
def delete_inventory_count(count_id):
    """Delete an inventory count"""
    counts = data_store.load_inventory_counts()
    counts = [c for c in counts if c.id != count_id]
    data_store.save_inventory_counts(counts)
    flash('Inventory count deleted', 'success')
    return redirect(url_for('orders_inventory'))


# ============ Order Sheet Routes ============

@app.route('/orders')
@login_required
def orders():
    """Redirect old orders URL to new combined page"""
    return redirect(url_for('orders_inventory'))


@app.route('/orders/sheet/<vendor_id>')
@login_required
def order_sheet(vendor_id):
    items = data_store.load_inventory()
    generator = OrderSheetGenerator(items)
    
    order = generator.generate_order_by_vendor(vendor_id)
    vendor = vendor_manager.get_vendor(vendor_id)
    
    if not order or not vendor:
        flash('Vendor not found', 'error')
        return redirect(url_for('orders'))
    
    return render_template('order_sheet.html', order=order, vendor=vendor)


@app.route('/orders/print/<vendor_id>')
@login_required
def print_order(vendor_id):
    items = data_store.load_inventory()
    generator = OrderSheetGenerator(items)
    
    order = generator.generate_order_by_vendor(vendor_id)
    vendor = vendor_manager.get_vendor(vendor_id)
    
    return render_template('order_print.html', order=order, vendor=vendor)


# ============ Vendor Routes ============

@app.route('/vendors')
@login_required
def vendors():
    """Redirect old vendors URL to new combined page"""
    return redirect(url_for('orders_inventory'))


@app.route('/vendors/add', methods=['POST'])
@manager_required
def add_vendor():
    from src.vendors import Vendor
    # Generate next vendor ID
    existing_ids = [v.id for v in vendor_manager.get_all_vendors()]
    next_num = 1
    while f'V{next_num:03d}' in existing_ids:
        next_num += 1
    vendor_id = f'V{next_num:03d}'
    
    categories = request.form.getlist('categories')
    
    vendor = Vendor(
        id=vendor_id,
        name=request.form.get('name', '').strip(),
        contact_name=request.form.get('contact_name', '').strip(),
        phone=request.form.get('phone', '').strip(),
        email=request.form.get('email', '').strip(),
        categories=categories,
        notes=request.form.get('notes', '').strip(),
        website_url=request.form.get('website_url', '').strip(),
        ordering_type='webview' if request.form.get('website_url', '').strip() else 'standard',
    )
    vendor_manager.add_vendor(vendor)
    flash(f'Vendor "{vendor.name}" added', 'success')
    return redirect(url_for('orders_inventory') + '?tab=vendors')


@app.route('/vendors/update/<vendor_id>', methods=['POST'])
@manager_required
def update_vendor(vendor_id):
    categories = request.form.getlist('categories')
    website_url = request.form.get('website_url', '').strip()
    update_kwargs = dict(
        name=request.form.get('name', ''),
        contact_name=request.form.get('contact_name', ''),
        phone=request.form.get('phone', ''),
        email=request.form.get('email', ''),
        categories=categories,
        notes=request.form.get('notes', ''),
        website_url=website_url,
    )
    # Auto-set ordering_type to webview if a URL is provided
    if website_url:
        update_kwargs['ordering_type'] = 'webview'
    vendor_manager.update_vendor(vendor_id, **update_kwargs)
    flash('Vendor updated', 'success')
    return redirect(url_for('orders_inventory') + '?tab=vendors')


@app.route('/vendors/delete/<vendor_id>', methods=['POST'])
@manager_required
def delete_vendor(vendor_id):
    if vendor_manager.delete_vendor(vendor_id):
        flash('Vendor deleted', 'success')
    else:
        flash('Vendor not found', 'error')
    return redirect(url_for('orders_inventory'))


# ============ User Management Routes ============

@app.route('/users')
@manager_required
def users():
    user_list = auth_manager.get_all_users()
    return render_template('users.html', users=user_list)


@app.route('/users/add', methods=['POST'])
@manager_required
def add_user():
    name = request.form.get('name')
    password = request.form.get('password')
    role = request.form.get('role', 'staff')
    
    if auth_manager.add_user(name, password, role):
        flash(f'User {name} added', 'success')
    else:
        flash('Password already in use', 'error')
    
    return redirect(url_for('users'))


@app.route('/users/delete/<user_id>', methods=['POST'])
@manager_required
def delete_user(user_id):
    if auth_manager.delete_user(user_id):
        flash('User removed', 'success')
    else:
        flash('Could not remove user', 'error')
    return redirect(url_for('users'))


# ============ API Routes for AJAX ============

@app.route('/api/shifts/<date_str>')
@login_required
def api_shifts(date_str):
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    shifts = data_store.load_shifts()
    day_shifts = [s for s in shifts if s.date == target_date]
    
    return jsonify([{
        'id': s.id,
        'employee_name': s.employee_name,
        'start_time': s.start_time.strftime('%I:%M %p'),
        'end_time': s.end_time.strftime('%I:%M %p'),
        'shift_type': s.shift_type.value
    } for s in day_shifts])


@app.route('/api/low-stock')
@login_required
def api_low_stock():
    items = data_store.load_inventory()
    low = [i for i in items if i.is_low_stock]
    
    return jsonify([{
        'id': i.id,
        'name': i.name,
        'quantity': i.quantity,
        'min_quantity': i.min_quantity,
        'unit': i.unit,
        'category': i.category.value
    } for i in low])


# ============ Invoice Routes ============

@app.route('/invoices')
@login_required
def invoices_page():
    """Invoice management with OCR"""
    invoices = invoice_manager.load_invoices()
    vendors = vendor_manager.get_all_vendors()
    # Sort newest first
    invoices.sort(key=lambda x: x.uploaded_at, reverse=True)
    return render_template('invoices.html',
                         invoices=invoices,
                         vendors=vendors,
                         tesseract_available=is_tesseract_available())


@app.route('/invoices/upload', methods=['POST'])
@login_required
def upload_invoice():
    """Upload and OCR-parse an invoice image"""
    vendor_name = request.form.get('vendor_name', '')
    
    if 'invoice_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('invoices_page'))
    
    file = request.files['invoice_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('invoices_page'))
    
    try:
        image_data = file.read()
        
        # OCR the invoice
        raw_text = invoice_parser.extract_text(image_data)
        
        # Parse the text into an invoice
        invoice = invoice_parser.parse_invoice_text(raw_text, vendor_name)
        
        # Try to match line items to inventory
        inventory_items = data_store.load_inventory()
        invoice = invoice_parser.match_to_inventory(invoice, inventory_items)
        
        # Save
        invoice_manager.add_invoice(invoice)
        
        flash(f'Invoice parsed: {invoice.item_count} items found, {invoice.matched_count} matched to inventory', 'success')
        return redirect(url_for('review_invoice', invoice_id=invoice.id))
    
    except Exception as e:
        flash(f'Error processing invoice: {str(e)}', 'error')
        return redirect(url_for('invoices_page'))


@app.route('/invoices/manual', methods=['POST'])
@login_required
def manual_invoice():
    """Manually create an invoice entry (paste text or enter items)"""
    vendor_name = request.form.get('vendor_name', '')
    raw_text = request.form.get('raw_text', '')
    invoice_number = request.form.get('invoice_number', '')
    
    if raw_text:
        invoice = invoice_parser.parse_invoice_text(raw_text, vendor_name)
    else:
        import uuid
        invoice = Invoice(
            id=str(uuid.uuid4())[:8].upper(),
            vendor_name=vendor_name,
        )
    
    invoice.invoice_number = invoice_number
    
    # Try to match
    inventory_items = data_store.load_inventory()
    invoice = invoice_parser.match_to_inventory(invoice, inventory_items)
    
    invoice_manager.add_invoice(invoice)
    flash(f'Invoice created: {invoice.item_count} items parsed', 'success')
    return redirect(url_for('review_invoice', invoice_id=invoice.id))


@app.route('/invoices/<invoice_id>')
@login_required
def review_invoice(invoice_id):
    """Review and edit a parsed invoice before applying"""
    invoice = invoice_manager.get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'error')
        return redirect(url_for('invoices_page'))
    
    inventory_items = data_store.load_inventory()
    vendors = vendor_manager.get_all_vendors()
    
    return render_template('invoice_review.html',
                         invoice=invoice,
                         inventory_items=inventory_items,
                         vendors=vendors)


@app.route('/invoices/<invoice_id>/match', methods=['POST'])
@login_required
def update_invoice_match(invoice_id):
    """Update a line item's inventory match"""
    invoice = invoice_manager.get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'error')
        return redirect(url_for('invoices_page'))
    
    line_index = int(request.form.get('line_index', -1))
    inventory_id = request.form.get('inventory_id', '')
    
    if 0 <= line_index < len(invoice.line_items):
        if inventory_id:
            inventory_items = data_store.load_inventory()
            matched = next((i for i in inventory_items if i.id == inventory_id), None)
            if matched:
                invoice.line_items[line_index].matched_inventory_id = matched.id
                invoice.line_items[line_index].matched_inventory_name = matched.name
        else:
            invoice.line_items[line_index].matched_inventory_id = ''
            invoice.line_items[line_index].matched_inventory_name = ''
        
        invoice_manager.update_invoice(invoice)
        flash('Match updated', 'success')
    
    return redirect(url_for('review_invoice', invoice_id=invoice_id))


@app.route('/invoices/<invoice_id>/edit-item', methods=['POST'])
@login_required
def edit_invoice_item(invoice_id):
    """Edit a line item's price or quantity"""
    invoice = invoice_manager.get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'error')
        return redirect(url_for('invoices_page'))
    
    line_index = int(request.form.get('line_index', -1))
    
    if 0 <= line_index < len(invoice.line_items):
        item = invoice.line_items[line_index]
        item.description = request.form.get('description', item.description)
        item.quantity = float(request.form.get('quantity', item.quantity) or 0)
        item.unit_price = float(request.form.get('unit_price', item.unit_price) or 0)
        item.total_price = float(request.form.get('total_price', item.total_price) or 0)
        item.unit = request.form.get('unit', item.unit)
        
        invoice_manager.update_invoice(invoice)
        flash('Item updated', 'success')
    
    return redirect(url_for('review_invoice', invoice_id=invoice_id))


@app.route('/invoices/<invoice_id>/apply', methods=['POST'])
@login_required
def apply_invoice(invoice_id):
    """Apply invoice prices to inventory items"""
    invoice = invoice_manager.get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'error')
        return redirect(url_for('invoices_page'))
    
    inventory_items = data_store.load_inventory()
    items_by_id = {item.id: item for item in inventory_items}
    
    updates_applied = []
    
    for line_item in invoice.line_items:
        if not line_item.matched_inventory_id:
            continue
        
        inv_item = items_by_id.get(line_item.matched_inventory_id)
        if not inv_item:
            continue
        
        old_price = inv_item.cost_per_unit
        new_price = line_item.unit_price
        
        if new_price > 0 and new_price != old_price:
            inv_item.cost_per_unit = new_price
            inv_item.last_updated = datetime.now()
            
            updates_applied.append({
                'item_name': inv_item.name,
                'item_id': inv_item.id,
                'old_price': old_price,
                'new_price': new_price,
                'change': round(new_price - old_price, 2),
                'change_pct': round(((new_price - old_price) / old_price * 100) if old_price > 0 else 0, 1),
            })
    
    # Save updated inventory
    data_store.save_inventory(inventory_items)
    
    # Mark invoice as applied
    invoice.status = 'applied'
    invoice.applied_updates = updates_applied
    invoice_manager.update_invoice(invoice)
    
    flash(f'Invoice applied: {len(updates_applied)} prices updated', 'success')
    return redirect(url_for('review_invoice', invoice_id=invoice_id))


@app.route('/invoices/<invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    """Delete an invoice"""
    invoice_manager.delete_invoice(invoice_id)
    flash('Invoice deleted', 'success')
    return redirect(url_for('invoices_page'))


# ============ Ordering Interface Routes ============

@app.route('/ordering')
@login_required
def ordering():
    """Ordering interface - select a vendor to order from"""
    ordering_vendors = vendor_manager.get_ordering_vendors()
    selected_vendor_id = request.args.get('vendor', '')
    
    selected_vendor = None
    vendor_data = {}
    
    if selected_vendor_id:
        selected_vendor = vendor_manager.get_vendor(selected_vendor_id)
    
    if selected_vendor and selected_vendor.ordering_type == 'kehe':
        # Load KeHE-specific data
        config = kehe_manager.load_config()
        warehouses = kehe_manager.get_warehouses()
        products = kehe_manager.load_products()
        orders = kehe_manager.load_orders()
        draft_order = kehe_manager.get_draft_order()
        inventory_items = data_store.load_inventory()
        inventory_mapping = kehe_manager.load_inventory_mapping()
        catalog_meta = kehe_manager.load_catalog_meta()
        
        search_query = request.args.get('search', '')
        if search_query:
            products = kehe_manager.search_products(search_query)
        
        low_stock_mapped = []
        for item in inventory_items:
            if item.is_low_stock:
                kehe_sku = inventory_mapping.get(item.id)
                if kehe_sku:
                    kehe_product = kehe_manager.get_product(kehe_sku)
                    if kehe_product:
                        low_stock_mapped.append({
                            'inventory_name': item.name,
                            'current_qty': item.quantity,
                            'unit': item.unit,
                            'kehe_product': kehe_product
                        })
        
        vendor_data = {
            'config': config,
            'warehouses': warehouses,
            'products': products,
            'orders': [o for o in orders if o.status != 'draft'],
            'draft_order': draft_order,
            'inventory_items': inventory_items,
            'inventory_mapping': inventory_mapping,
            'low_stock_mapped': low_stock_mapped,
            'search_query': search_query,
            'catalog_meta': catalog_meta,
        }
    elif selected_vendor and selected_vendor.ordering_type == 'catalog':
        # Load catalog-based vendor ordering data
        products = vendor_order_manager.load_products(selected_vendor_id)
        draft_order = vendor_order_manager.get_draft_order(selected_vendor_id)
        past_orders = vendor_order_manager.get_orders(selected_vendor_id)
        
        # Get unique categories for filter
        categories = sorted(set(p.category for p in products if p.category))
        
        search_query = request.args.get('search', '')
        if search_query:
            products = vendor_order_manager.search_products(selected_vendor_id, search_query)
        
        vendor_data = {
            'products': products,
            'draft_order': draft_order,
            'past_orders': past_orders,
            'categories': categories,
            'search_query': search_query,
        }
    elif selected_vendor and selected_vendor.ordering_type == 'standard':
        # Load standard vendor order data
        items = data_store.load_inventory()
        from src.order_sheet import OrderSheetGenerator
        generator = OrderSheetGenerator(items)
        order = generator.generate_order_by_vendor(selected_vendor_id)
        vendor_data = {
            'order': order,
            'items': items,
        }
    
    return render_template('ordering.html',
                         ordering_vendors=ordering_vendors,
                         selected_vendor=selected_vendor,
                         vendor_data=vendor_data)


@app.route('/ordering/toggle/<vendor_id>', methods=['POST'])
@login_required
def toggle_vendor_ordering(vendor_id):
    """Enable or disable ordering for a vendor"""
    vendor = vendor_manager.get_vendor(vendor_id)
    if vendor:
        vendor_manager.update_vendor(vendor_id, ordering_enabled=not vendor.ordering_enabled)
        status = 'enabled' if not vendor.ordering_enabled else 'disabled'
        flash(f'Ordering {status} for {vendor.name}', 'success')
    return redirect(url_for('ordering'))


# ============ Vendor Catalog Routes ============

def _catalog_redirect(vendor_id, tab=None):
    """Helper to build redirect URL back to the ordering page for a catalog vendor."""
    params = {'vendor': vendor_id}
    if tab:
        params['tab'] = tab
    return redirect(url_for('ordering', **params))


@app.route('/vendor-catalog/<vendor_id>/product/add', methods=['POST'])
@login_required
def vendor_catalog_add_product(vendor_id):
    """Add a product to a vendor's catalog"""
    import uuid
    product = VendorProduct(
        id=str(uuid.uuid4())[:8].upper(),
        vendor_id=vendor_id,
        name=request.form.get('name', ''),
        sku=request.form.get('sku', ''),
        description=request.form.get('description', ''),
        category=request.form.get('category', ''),
        unit=request.form.get('unit', 'each'),
        pack_size=request.form.get('pack_size', ''),
        cost=float(request.form.get('cost', 0) or 0)
    )
    vendor_order_manager.add_product(product)
    flash(f'Product "{product.name}" added to catalog', 'success')
    return _catalog_redirect(vendor_id, tab='catalog')


@app.route('/vendor-catalog/<vendor_id>/product/<product_id>/edit', methods=['POST'])
@login_required
def vendor_catalog_edit_product(vendor_id, product_id):
    """Edit a product in a vendor's catalog"""
    vendor_order_manager.update_product(product_id,
        name=request.form.get('name', ''),
        sku=request.form.get('sku', ''),
        description=request.form.get('description', ''),
        category=request.form.get('category', ''),
        unit=request.form.get('unit', 'each'),
        pack_size=request.form.get('pack_size', ''),
        cost=float(request.form.get('cost', 0) or 0)
    )
    flash('Product updated', 'success')
    return _catalog_redirect(vendor_id, tab='catalog')


@app.route('/vendor-catalog/<vendor_id>/product/<product_id>/delete', methods=['POST'])
@login_required
def vendor_catalog_delete_product(vendor_id, product_id):
    """Delete a product from vendor catalog"""
    vendor_order_manager.delete_product(product_id)
    flash('Product removed from catalog', 'success')
    return _catalog_redirect(vendor_id, tab='catalog')


@app.route('/vendor-catalog/<vendor_id>/order/create', methods=['POST'])
@login_required
def vendor_catalog_create_order(vendor_id):
    """Create a new draft order for a vendor"""
    vendor = vendor_manager.get_vendor(vendor_id)
    if vendor:
        order = vendor_order_manager.create_order(vendor_id, vendor.name)
        flash(f'Draft order created', 'success')
    return _catalog_redirect(vendor_id)


@app.route('/vendor-catalog/<vendor_id>/order/<order_id>/add', methods=['POST'])
@login_required
def vendor_catalog_add_item(vendor_id, order_id):
    """Add item to a vendor order"""
    product_id = request.form.get('product_id', '')
    quantity = int(request.form.get('quantity', 1))
    product = vendor_order_manager.get_product(product_id)
    if product:
        vendor_order_manager.add_item_to_order(order_id, product, quantity)
        flash(f'{product.name} added to order', 'success')
    else:
        flash('Product not found', 'error')
    return _catalog_redirect(vendor_id)


@app.route('/vendor-catalog/<vendor_id>/order/<order_id>/remove/<product_id>', methods=['POST'])
@login_required
def vendor_catalog_remove_item(vendor_id, order_id, product_id):
    """Remove item from vendor order"""
    vendor_order_manager.remove_item_from_order(order_id, product_id)
    flash('Item removed from order', 'success')
    return _catalog_redirect(vendor_id)


@app.route('/vendor-catalog/<vendor_id>/order/<order_id>/submit', methods=['POST'])
@login_required
def vendor_catalog_submit_order(vendor_id, order_id):
    """Submit a vendor order"""
    po_number = request.form.get('po_number', '')
    notes = request.form.get('notes', '')
    vendor_order_manager.submit_order(order_id, po_number, notes)
    flash('Order submitted!', 'success')
    return _catalog_redirect(vendor_id, tab='history')


@app.route('/vendor-catalog/<vendor_id>/order/<order_id>/received', methods=['POST'])
@login_required
def vendor_catalog_received_order(vendor_id, order_id):
    """Mark a vendor order as received"""
    vendor_order_manager.mark_received(order_id)
    flash('Order marked as received', 'success')
    return _catalog_redirect(vendor_id, tab='history')


@app.route('/vendor-catalog/<vendor_id>/order/<order_id>/delete', methods=['POST'])
@login_required
def vendor_catalog_delete_order(vendor_id, order_id):
    """Delete a vendor order"""
    vendor_order_manager.delete_order(order_id)
    flash('Order deleted', 'success')
    return _catalog_redirect(vendor_id)


@app.route('/vendor-catalog/<vendor_id>/order/<order_id>/print')
@login_required
def vendor_catalog_print_order(vendor_id, order_id):
    """Print view for a vendor order"""
    vendor = vendor_manager.get_vendor(vendor_id)
    orders = vendor_order_manager._load_all_orders()
    order = next((o for o in orders if o.id == order_id), None)
    if not order:
        flash('Order not found', 'error')
        return _catalog_redirect(vendor_id)
    return render_template('vendor_order_print.html', vendor=vendor, order=order)


# ============ KeHE Routes ============

def _kehe_redirect(tab=None):
    """Helper to build redirect URL back to the ordering page for KeHE vendor."""
    kehe_vendor = next((v for v in vendor_manager.get_all_vendors() if v.ordering_type == 'kehe'), None)
    vendor_id = kehe_vendor.id if kehe_vendor else ''
    params = {'vendor': vendor_id}
    if tab:
        params['tab'] = tab
    return redirect(url_for('ordering', **params))

@app.route('/kehe')
@login_required
def kehe():
    """KeHE ordering - redirect to unified ordering page"""
    return _kehe_redirect()


@app.route('/kehe/settings', methods=['POST'])
@login_required
def kehe_save_settings():
    """Save KeHE settings"""
    from src.kehe import KeHEConfig
    config = KeHEConfig(
        account_number=request.form.get('account_number', ''),
        username=request.form.get('username', ''),
        primary_warehouse=request.form.get('primary_warehouse', ''),
        default_delivery_instructions=request.form.get('delivery_instructions', '')
    )
    kehe_manager.save_config(config)
    flash('KeHE settings saved', 'success')
    return _kehe_redirect()


@app.route('/kehe/warehouse', methods=['POST'])
@login_required
def kehe_select_warehouse():
    """Select warehouse for ordering"""
    config = kehe_manager.load_config()
    config.primary_warehouse = request.form.get('warehouse', '')
    kehe_manager.save_config(config)
    flash(f'Warehouse set to {config.primary_warehouse}', 'success')
    return _kehe_redirect()


@app.route('/kehe/product/add', methods=['POST'])
@login_required
def kehe_add_product():
    """Add a product to KeHE catalog"""
    warehouse_codes = [w.strip() for w in request.form.get('warehouse_codes', '').split(',') if w.strip()]
    
    product = KeHEProduct(
        sku=request.form.get('sku', ''),
        upc=request.form.get('upc', ''),
        name=request.form.get('name', ''),
        brand=request.form.get('brand', ''),
        category=request.form.get('category', ''),
        pack_size=request.form.get('pack_size', ''),
        case_cost=float(request.form.get('case_cost', 0)),
        unit_cost=float(request.form.get('unit_cost', 0)),
        units_per_case=int(request.form.get('units_per_case', 12)),
        warehouse_codes=warehouse_codes
    )
    kehe_manager.add_product(product)
    flash(f'Product {product.name} added to catalog', 'success')
    return _kehe_redirect(tab='products')


@app.route('/kehe/order/create', methods=['POST'])
@login_required
def kehe_create_order():
    """Create a new KeHE order"""
    warehouse = request.form.get('warehouse', '')
    if not warehouse:
        config = kehe_manager.load_config()
        warehouse = config.primary_warehouse
    
    if not warehouse:
        flash('Please select a warehouse first', 'error')
        return _kehe_redirect()
    
    order = kehe_manager.create_order(warehouse)
    flash(f'Order {order.id} created', 'success')
    return _kehe_redirect()


@app.route('/kehe/order/<order_id>/add', methods=['POST'])
@login_required
def kehe_add_item(order_id):
    """Add item to order"""
    sku = request.form.get('sku', '')
    quantity = int(request.form.get('quantity', 1))
    
    if kehe_manager.add_item_to_order(order_id, sku, quantity):
        flash('Item added to order', 'success')
    else:
        flash('Failed to add item', 'error')
    
    return _kehe_redirect()


@app.route('/kehe/order/<order_id>/remove/<sku>', methods=['POST'])
@login_required
def kehe_remove_item(order_id, sku):
    """Remove item from order"""
    kehe_manager.remove_item_from_order(order_id, sku)
    flash('Item removed', 'success')
    return _kehe_redirect()


@app.route('/kehe/order/<order_id>/submit', methods=['POST'])
@login_required
def kehe_submit_order(order_id):
    """Submit order to KeHE"""
    po_number = request.form.get('po_number', '')
    kehe_manager.update_order_status(order_id, 'submitted', po_number)
    flash('Order submitted! Download the CSV to upload to KeHE CONNECT.', 'success')
    return _kehe_redirect()


@app.route('/kehe/order/<order_id>/delete', methods=['POST'])
@login_required
def kehe_delete_order(order_id):
    """Delete draft order"""
    kehe_manager.delete_order(order_id)
    flash('Order deleted', 'success')
    return _kehe_redirect()


@app.route('/kehe/order/<order_id>/download')
@login_required
def kehe_download_order(order_id):
    """Download order as CSV"""
    csv_content = kehe_manager.generate_order_csv(order_id)
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=kehe_order_{order_id}.csv'}
    )


@app.route('/kehe/quick-add', methods=['POST'])
@login_required
def kehe_quick_add():
    """Quick add low stock item to order"""
    sku = request.form.get('sku', '')
    quantity = int(request.form.get('quantity', 1))
    
    draft_order = kehe_manager.get_draft_order()
    if not draft_order:
        config = kehe_manager.load_config()
        if config.primary_warehouse:
            draft_order = kehe_manager.create_order(config.primary_warehouse)
        else:
            flash('Please select a warehouse first', 'error')
            return _kehe_redirect()
    
    if kehe_manager.add_item_to_order(draft_order.id, sku, quantity):
        flash('Item added to order', 'success')
    else:
        flash('Failed to add item', 'error')
    
    return _kehe_redirect()


@app.route('/kehe/map', methods=['POST'])
@login_required
def kehe_map_inventory():
    """Map inventory item to KeHE product"""
    inventory_id = request.form.get('inventory_id', '')
    kehe_sku = request.form.get('kehe_sku', '')
    
    if inventory_id and kehe_sku:
        kehe_manager.map_inventory_to_kehe(inventory_id, kehe_sku)
        flash('Inventory mapped to KeHE product', 'success')
    
    return _kehe_redirect(tab='products')


@app.route('/kehe/catalog/refresh', methods=['POST'])
@login_required
def kehe_refresh_catalog():
    """Refresh KeHE catalog"""
    result = kehe_manager.refresh_catalog()
    flash(f'Catalog refreshed: {result["total_products"]} products, {result["active_products"]} active', 'success')
    return _kehe_redirect(tab='products')


@app.route('/kehe/catalog/import', methods=['POST'])
@login_required
def kehe_import_csv():
    """Import KeHE catalog from CSV file"""
    if 'csv_file' not in request.files:
        flash('No file uploaded', 'error')
        return _kehe_redirect(tab='products')
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return _kehe_redirect(tab='products')
    
    # Check if we should clear existing catalog
    if request.form.get('clear_existing'):
        kehe_manager.clear_catalog()
    
    # Read and decode CSV content
    try:
        csv_content = file.read().decode('utf-8')
    except:
        try:
            file.seek(0)
            csv_content = file.read().decode('latin-1')
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return _kehe_redirect(tab='products')
    
    # Get warehouse preference
    warehouse = request.form.get('warehouse', '')
    
    # Import the catalog
    result = kehe_manager.import_catalog_csv(csv_content, warehouse if warehouse else None)
    
    flash(f'Import complete: {result["added"]} added, {result["updated"]} updated, {result["skipped"]} skipped. Total: {result["total"]} products', 'success')
    
    if result['errors']:
        for error in result['errors'][:3]:  # Show first 3 errors
            flash(error, 'warning')
    
    return _kehe_redirect(tab='products')


@app.route('/kehe/product/<sku>/stock', methods=['POST'])
@login_required
def kehe_toggle_stock(sku):
    """Toggle product stock status"""
    action = request.form.get('action', '')
    if action == 'available':
        kehe_manager.mark_product_available(sku)
        flash('Product marked as available', 'success')
    elif action == 'unavailable':
        kehe_manager.mark_product_unavailable(sku)
        flash('Product marked as out of stock', 'success')
    return _kehe_redirect(tab='products')


@app.route('/kehe/product/<sku>/delete', methods=['POST'])
@login_required
def kehe_delete_product(sku):
    """Delete product from catalog"""
    kehe_manager.delete_product(sku)
    flash('Product removed from catalog', 'success')
    return _kehe_redirect(tab='products')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
