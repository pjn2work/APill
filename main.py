import flet as ft
import flet_audio as fta
import json
import os
import asyncio
from datetime import datetime, timedelta
import uuid

# ================= CONFIG & CONSTANTS =================
STORAGE_FILE = "pills_data.json"
ALARM_CHECK_INTERVAL = 10  # seconds
TIMELINE_SCALE = 1.0  # pixels per minute of spacing

# Category colors: (main_color, light_background_color)
CATEGORIES = {
    "primary": (ft.Colors.BLUE_400, ft.Colors.BLUE_50),
    "secondary": (ft.Colors.GREEN_400, ft.Colors.GREEN_50),
    "tertiary": (ft.Colors.ORANGE_400, ft.Colors.ORANGE_50),
    "quaternary": (ft.Colors.RED_400, ft.Colors.RED_50),
}


# ================= DATA MANAGER =================
class PillManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                data = json.load(f)
                self.categories = data.get("categories", {
                    "primary": "Primary",
                    "secondary": "Secondary",
                    "tertiary": "Tertiary",
                    "quaternary": "Quaternary",
                })
                self.agenda = data.get("agenda", {})
                # Check and auto-disable completed pills
                self._check_and_disable_completed()
        else:
            self.categories = {
                "primary": "Primary",
                "secondary": "Secondary",
                "tertiary": "Tertiary",
                "quaternary": "Quaternary",
            }
            self.agenda = {}
            self._save()

    def _check_and_disable_completed(self):
        """Auto-disable pills that have completed all their doses, and sync completed_takes."""
        changed = False
        for pill_id, p in self.agenda.items():
            expected_takes = self._calculate_expected_takes_from_pill(p)

            # Sync completed_takes to JSON
            if p.get("completed_takes", 0) != expected_takes:
                p["completed_takes"] = expected_takes
                changed = True

            if not p.get("active", True):
                continue

            total_takes = p["duration_days"] * p["times_per_day"]
            if expected_takes >= total_takes:
                p["active"] = False
                changed = True

        if changed:
            self._save()

    def _calculate_expected_takes_from_pill(self, pill):
        """Helper to calculate expected takes from a pill dict"""
        return calculate_expected_takes(pill)

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump({
                "categories": self.categories,
                "agenda": self.agenda
            }, f, indent=2)

    def get_all(self):
        # Return pills with their ID added back (UI expects it)
        pills = []
        for pill_id, pill_data in self.agenda.items():
            pill = dict(pill_data)  # Create a copy
            pill["id"] = pill_id  # Add the ID from the key
            pills.append(pill)
        return pills

    def add_pill(self, pill_data):
        pill_id = str(uuid.uuid4())
        # Don't store ID inside pill_data, it's the key
        if "id" in pill_data:
            del pill_data["id"]
        pill_data.setdefault("completed_takes", 0)
        pill_data["last_alarm_time"] = None
        pill_data["snoozed_until"] = None
        pill_data["active"] = True
        pill_data.setdefault("start_date", datetime.now().date().isoformat())
        self.agenda[pill_id] = pill_data
        self._save()

    def update_pill(self, pill_id, pill_data):
        if pill_id in self.agenda:
            self.agenda[pill_id].update(pill_data)
            self._save()
            return True
        return False

    def delete_pill(self, pill_id):
        if pill_id in self.agenda:
            del self.agenda[pill_id]
            self._save()

    def mark_done(self, pill_id):
        if pill_id in self.agenda:
            p = self.agenda[pill_id]
            p["last_alarm_time"] = datetime.now().isoformat()
            p["snoozed_until"] = None

            # Persist the calculated count so the JSON stays accurate
            expected_takes = self._calculate_expected_takes_from_pill(p)
            p["completed_takes"] = expected_takes

            total_takes = p["duration_days"] * p["times_per_day"]
            if expected_takes >= total_takes:
                p["active"] = False

            self._save()
            return True
        return False

    def snooze_pill(self, pill_id, snooze_duration_min=10):
        if pill_id in self.agenda:
            p = self.agenda[pill_id]
            p["snoozed_until"] = (datetime.now() + timedelta(minutes=snooze_duration_min)).isoformat()
            p["last_alarm_time"] = datetime.now().isoformat()
            self._save()
            return True
        return False

    def get_categories(self):
        return self.categories

    def update_category_name(self, category_key, new_name):
        if category_key in self.categories:
            self.categories[category_key] = new_name
            self._save()
            return True
        return False

    def toggle_pill_active(self, pill_id):
        """Toggle the active state of a pill"""
        if pill_id in self.agenda:
            p = self.agenda[pill_id]
            was_inactive = not p.get("active", True)
            p["active"] = not p.get("active", True)

            # If enabling a pill that was disabled, check if it needs a new start_date
            if was_inactive and p["active"]:
                total_takes = p["duration_days"] * p["times_per_day"]
                expected_takes = self._calculate_expected_takes_from_pill(p)

                # If all doses are already completed, reset start_date to today
                if expected_takes >= total_takes:
                    p["start_date"] = datetime.now().date().isoformat()
                    p["last_alarm_time"] = None
                    p["snoozed_until"] = None

            self._save()
            return True
        return False


# ================= SCHEDULE CALCULATOR =================
def get_today_schedule(pill):
    """Returns list of datetime objects for today's scheduled takes"""
    start = pill["start_time"].split(":")
    interval = (24 * 60) / pill["times_per_day"]  # minutes between doses

    # Create a base time for today at midnight
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Calculate the first dose time in minutes from midnight
    start_minutes = int(start[0]) * 60 + int(start[1])

    times = []
    for i in range(pill["times_per_day"]):
        # Calculate minutes from midnight for this dose
        dose_minutes = (start_minutes + i * interval) % (24 * 60)

        # Create the time for today
        t = today_midnight + timedelta(minutes=dose_minutes)
        times.append(t)

    # Sort times chronologically
    times.sort()
    return times


def get_next_alarm(pill):
    """Returns the next scheduled datetime for this pill"""
    now = datetime.now()
    today_times = get_today_schedule(pill)
    for t in today_times:
        if t > now:
            return t
    # If all today's times passed, schedule tomorrow's first
    tomorrow = (now + timedelta(days=1)).replace(
        hour=int(pill["start_time"].split(":")[0]),
        minute=int(pill["start_time"].split(":")[1]),
        second=0, microsecond=0
    )
    return tomorrow


def calculate_expected_takes(pill):
    """Calculate how many doses should have been taken based on start_date+start_time to now."""
    start_date_str = pill.get("start_date")
    if not start_date_str:
        return pill.get("completed_takes", 0)

    from datetime import date
    start_date = date.fromisoformat(start_date_str)
    start_hh, start_mm = pill["start_time"].split(":")
    start_dt = datetime(start_date.year, start_date.month, start_date.day,
                        int(start_hh), int(start_mm))
    current_dt = datetime.now()

    if current_dt < start_dt:
        return 0

    # Precompute dose offsets in minutes from midnight (same pattern every day)
    interval_min = (24 * 60) / pill["times_per_day"]
    start_min = int(start_hh) * 60 + int(start_mm)
    dose_offsets = [(start_min + i * interval_min) % (24 * 60)
                    for i in range(pill["times_per_day"])]

    count = 0
    d = start_date
    while d <= current_dt.date():
        midnight = datetime(d.year, d.month, d.day)
        for dm in dose_offsets:
            dose_dt = midnight + timedelta(minutes=dm)
            if start_dt <= dose_dt <= current_dt:
                count += 1
        d += timedelta(days=1)
    return count


# ================= ALARM CHECKER =================
async def alarm_loop(page, manager):
    """Background task that checks for due alarms"""
    while True:
        await asyncio.sleep(ALARM_CHECK_INTERVAL)

        # Check and auto-disable completed pills
        manager._check_and_disable_completed()

        now = datetime.now()
        pills = manager.get_all()

        for pill in pills:
            if not pill.get("active", True):
                continue

            # Check snooze
            snooze_until = pill.get("snoozed_until")
            if snooze_until:
                snooze_until_dt = datetime.fromisoformat(snooze_until)
                if now < snooze_until_dt:
                    continue  # Still snoozed
                # Snooze expired — clear it and fire alarm
                manager.update_pill(pill["id"], {"snoozed_until": None})
                total_takes = pill["duration_days"] * pill["times_per_day"]
                completed = calculate_expected_takes(pill)
                remaining = total_takes - completed
                show_alarm_modal(page, pill, remaining, now.strftime("%H:%M"))
                continue

            next_alarm = get_next_alarm(pill)
            if next_alarm - now <= timedelta(seconds=ALARM_CHECK_INTERVAL):
                total_takes = pill["duration_days"] * pill["times_per_day"]
                completed = calculate_expected_takes(pill)
                remaining = total_takes - completed
                show_alarm_modal(page, pill, remaining, next_alarm.strftime("%H:%M"))


# ================= UI COMPONENTS =================
def gradient_header(title, leading=None):
    """Rounded gradient header bar (blue → magenta)."""
    return ft.Container(
        content=ft.Stack([
            ft.Container(
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, 0),
                    end=ft.Alignment(1, 0),
                    colors=["#1565C0", "#3C1FA2", "#7B1FA2"],
                ),
                border_radius=ft.BorderRadius(24, 24, 10, 10),
                padding=ft.Padding(16, 12, 16, 16),
            ),
            ft.Container(
                content=ft.Row([
                    leading if leading else ft.Container(width=40),
                    ft.Text(title, size=18, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE, expand=True,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(width=40),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(8, 12, 8, 16),
            ),
        ]),
        height=60,
    )


def show_alarm_modal(page, pill, remaining, take_time):
    if alarm_audio:
        asyncio.create_task(alarm_audio.play())

    dlg = ft.AlertDialog(
        title=ft.Text(f"⏰ Take {pill['name']}", size=20),
        content=ft.Column([
            ft.Text(f"📅 Time: {take_time}", weight=ft.FontWeight.BOLD),
            ft.Text(f"📝 {pill['description']}"),
            ft.Text(f"💊 Remaining takes: {remaining}"),
            ft.Divider(),
            ft.Row([
                ft.FilledButton("🔔 Snooze 10min",
                                  icon=ft.icons.Icons.ACCESS_TIME,
                                  on_click=lambda e, p=pill["id"]: _handle_snooze(page, p)),
                ft.FilledButton("✅ Done",
                                  icon=ft.icons.Icons.CHECK,
                                  bgcolor=ft.Colors.GREEN_400,
                                  color=ft.Colors.WHITE,
                                  on_click=lambda e, p=pill["id"]: _handle_done(page, p)),
            ], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        ], tight=True),
        on_dismiss=lambda e: (_stop_alarm(), page.update()),
    )
    page.show_dialog(dlg)


def _stop_alarm():
    if alarm_audio:
        asyncio.create_task(alarm_audio.pause())


def _handle_snooze(page, pill_id):
    _stop_alarm()
    manager.snooze_pill(pill_id)
    page.pop_dialog()
    snack_bar = ft.SnackBar(content=ft.Text("Snoozed for 10 minutes"), open=True)
    page.overlay.append(snack_bar)
    page.update()


def _handle_done(page, pill_id):
    _stop_alarm()
    manager.mark_done(pill_id)
    page.pop_dialog()
    snack_bar = ft.SnackBar(content=ft.Text("Marked as taken!"), open=True)
    page.overlay.append(snack_bar)
    refresh_views(page)


def refresh_views(page):
    """Refresh both dashboards without reloading app"""
    # Get the current view and update its controls
    if page.views:
        current_view = page.views[-1]  # Get the topmost view

        if current_view.route == "/":
            # Update dashboard view
            new_view = create_dashboard_view(page)
            current_view.controls = new_view.controls
        elif current_view.route == "/timeline":
            # Update timeline view
            new_view = create_timeline_view(page)
            current_view.controls = new_view.controls
        elif current_view.route == "/categories":
            # Update categories view
            new_view = create_categories_view(page)
            current_view.controls = new_view.controls

        page.update()


def create_pill_form(page, pill_data=None):
    is_edit = pill_data is not None
    title = "Edit Pill" if is_edit else "Add New Pill"

    # Handle None pill_data
    if pill_data is None:
        pill_data = {}

    start_time = pill_data.get("start_time", "18:00")
    start_hh, start_mm = start_time.split(":")

    today = datetime.now().date()
    raw_date = pill_data.get("start_date", today.isoformat())
    sd = datetime.fromisoformat(raw_date).date()

    if is_edit:
        def save(e):
            manager.update_pill(pill_data["id"], {
                "name": name_ctrl.value.strip(),
                "description": desc_ctrl.value.strip(),
                "start_date": f"{year_ctrl.value.zfill(4)}-{mon_ctrl.value.zfill(2)}-{day_ctrl.value.zfill(2)}",
                "start_time": f"{hour_ctrl.value.zfill(2)}:{min_ctrl.value.zfill(2)}",
                "times_per_day": int(freq_ctrl.value or 1),
                "duration_days": int(days_ctrl.value or 1),
                "category": cat_ctrl.value,
            })
            page.pop_dialog()
            refresh_views(page)
    else:
        def save(e):
            manager.add_pill({
                "name": name_ctrl.value.strip(),
                "description": desc_ctrl.value.strip(),
                "start_date": f"{year_ctrl.value.zfill(4)}-{mon_ctrl.value.zfill(2)}-{day_ctrl.value.zfill(2)}",
                "start_time": f"{hour_ctrl.value.zfill(2)}:{min_ctrl.value.zfill(2)}",
                "times_per_day": int(freq_ctrl.value or 1),
                "duration_days": int(days_ctrl.value or 1),
                "category": cat_ctrl.value,
            })
            page.pop_dialog()
            refresh_views(page)

    name_ctrl = ft.TextField(label="Pill Name", value=pill_data.get("name", ""), hint_text="e.g. Ibuprofen")
    desc_ctrl = ft.TextField(label="Description/Notes", value=pill_data.get("description", ""),
                             hint_text="e.g. 1/2 After Dinner")
    year_ctrl = ft.TextField(label="YYYY", value=str(sd.year),
                             keyboard_type=ft.KeyboardType.NUMBER, expand=2)
    mon_ctrl  = ft.TextField(label="MM", value=str(sd.month).zfill(2),
                             keyboard_type=ft.KeyboardType.NUMBER, expand=1)
    day_ctrl  = ft.TextField(label="DD", value=str(sd.day).zfill(2),
                             keyboard_type=ft.KeyboardType.NUMBER, expand=1)
    hour_ctrl = ft.TextField(label="HH", value=start_hh,
                             keyboard_type=ft.KeyboardType.NUMBER, expand=1)
    min_ctrl  = ft.TextField(label="MM", value=start_mm,
                             keyboard_type=ft.KeyboardType.NUMBER, expand=1)
    freq_ctrl = ft.TextField(label="Times/Day", value=str(pill_data.get("times_per_day", 1)),
                             keyboard_type=ft.KeyboardType.NUMBER, expand=1)
    days_ctrl = ft.TextField(label="Days", value=str(pill_data.get("duration_days", 7)),
                             keyboard_type=ft.KeyboardType.NUMBER, expand=1)

    # Get category names from manager
    categories = manager.get_categories()
    cat_ctrl = ft.Dropdown(
        label="Category",
        options=[ft.dropdown.Option(key=k, text=categories.get(k, k)) for k in CATEGORIES.keys()],
        value=pill_data.get("category", "primary"),
        expand=True,
    )

    dlg = ft.AlertDialog(
        title=ft.Text(title, size=18),
        content=ft.Column([
            name_ctrl,
            desc_ctrl,
            ft.Text("Start Date", size=12, color=ft.Colors.GREY_600),
            ft.Row([year_ctrl, mon_ctrl, day_ctrl], spacing=8),
            ft.Text("Start Time", size=12, color=ft.Colors.GREY_600),
            ft.Row([hour_ctrl, min_ctrl], spacing=8),
            ft.Row([freq_ctrl, days_ctrl], spacing=8),
            cat_ctrl,
        ], tight=True, scroll=ft.ScrollMode.AUTO, width=300),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Save", icon=ft.icons.Icons.SAVE, on_click=save),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_EVENLY,
    )
    page.show_dialog(dlg)


def create_dashboard_view(page_ref=None):
    view = ft.View("/")

    def _toggle_pill(e, pill_id):
        manager.toggle_pill_active(pill_id)
        refresh_views(page_ref)

    def render_pills():
        pills = manager.get_all()
        active = [p for p in pills if p.get("active", True)]
        inactive = [p for p in pills if not p.get("active", True)]
        categories = manager.get_categories()

        # Sort by next alarm time, then by name
        active.sort(key=lambda p: (get_next_alarm(p), p["name"].lower()))
        inactive.sort(key=lambda p: p["name"].lower())

        controls = []

        # Active pills section
        if active:
            controls.append(ft.Text("Active Pills", size=18, weight=ft.FontWeight.BOLD))

        for p in active:
            # Calculate statistics
            total_takes = p["duration_days"] * p["times_per_day"]
            completed_takes = calculate_expected_takes(p)
            remaining_takes = total_takes - completed_takes

            # Get start date
            start_date_str = p.get("start_date", datetime.now().date().isoformat())
            start_date_display = datetime.fromisoformat(start_date_str).strftime("%Y-%m-%d")

            # Calculate last day
            import math
            remaining_days = math.ceil(remaining_takes / p["times_per_day"])
            last_day = datetime.now() + timedelta(days=remaining_days - 1)
            last_day_str = last_day.strftime("%Y-%m-%d")

            # Get category name
            category_name = categories.get(p["category"], p["category"])

            # Get next take time
            next_alarm = get_next_alarm(p)
            next_time_str = next_alarm.strftime("%H:%M")

            # Get all scheduled times for today
            times_today = get_today_schedule(p)
            times_str = ", ".join([t.strftime("%H:%M") for t in times_today])

            main_color, bg_color = CATEGORIES[p["category"]]

            row = ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        # Left: next take time
                        ft.Container(
                            content=ft.Column([
                                ft.Text(next_time_str, size=24, weight=ft.FontWeight.BOLD, color=main_color),
                                ft.Text("next take", size=10, color=ft.Colors.GREY_600),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            width=85,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.VerticalDivider(width=1, color=ft.Colors.GREY_300),
                        # Right: stacked info
                        ft.Column([
                            # Row 1: name (left) | category (right)
                            ft.Row([
                                ft.Text(p["name"], size=15, weight=ft.FontWeight.BOLD, expand=True),
                                ft.Text(category_name, size=10, color=ft.Colors.GREY_600),
                            ]),
                            # Row 2: description
                            ft.Row([
                                ft.Text(p["description"], size=11, color=ft.Colors.GREY_600, expand=True),
                            ]),
                            # Row 3: scheduled times (left) | buttons (right)
                            ft.Row([
                                ft.Text(times_str, size=11, weight=ft.FontWeight.W_500, color=main_color, expand=True),
                                ft.IconButton(
                                    icon=ft.icons.Icons.TOGGLE_ON,
                                    icon_color=ft.Colors.GREEN_600,
                                    icon_size=18,
                                    tooltip="Disable",
                                    on_click=lambda e, pid=p["id"]: _toggle_pill(e, pid)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.EDIT,
                                    icon_size=18,
                                    on_click=lambda e, p_data=p: _edit_pill(e, p_data)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.DELETE,
                                    icon_color=ft.Colors.RED_400,
                                    icon_size=18,
                                    on_click=lambda e, pid=p["id"]: _delete_pill(e, pid)
                                ),
                            ], spacing=0),
                            # Row 4: stats
                            ft.Row([
                                ft.Text(f"✓ {completed_takes}", size=10, color=ft.Colors.GREEN_600),
                                ft.Text("•", size=10, color=ft.Colors.GREY_400),
                                ft.Text(f"⏳ {remaining_takes}", size=10, color=ft.Colors.ORANGE_600),
                                ft.Text("•", size=10, color=ft.Colors.GREY_400),
                                ft.Text(f"🗓 {start_date_display}", size=10, color=ft.Colors.PURPLE_600),
                                ft.Text("•", size=10, color=ft.Colors.GREY_400),
                                ft.Text(f"📅 {last_day_str}", size=10, color=ft.Colors.BLUE_600),
                            ], spacing=3),
                        ], expand=True, spacing=2),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=10,
                    bgcolor=bg_color,
                ),
                margin=ft.Margin.only(bottom=8),
            )
            controls.append(row)

        # Inactive pills section
        if inactive:
            controls.append(ft.Container(height=20))
            controls.append(ft.Text("Disabled Pills", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600))

        for p in inactive:
            # Calculate statistics
            total_takes = p["duration_days"] * p["times_per_day"]
            completed_takes = calculate_expected_takes(p)
            remaining_takes = total_takes - completed_takes

            # Get start date
            start_date_str = p.get("start_date", datetime.now().date().isoformat())
            start_date_display = datetime.fromisoformat(start_date_str).strftime("%Y-%m-%d")

            # Calculate last day
            import math
            remaining_days = math.ceil(remaining_takes / p["times_per_day"]) if remaining_takes > 0 else 0
            last_day = datetime.now() + timedelta(days=remaining_days - 1)
            last_day_str = last_day.strftime("%Y-%m-%d")

            # Get category name
            category_name = categories.get(p["category"], p["category"])

            # Get all scheduled times for today
            times_today = get_today_schedule(p)
            times_str = ", ".join([t.strftime("%H:%M") for t in times_today])

            main_color, bg_color = CATEGORIES[p["category"]]

            row = ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        # Pill info (full width since no next time)
                        ft.Column([
                            ft.Text(p["name"], size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600),
                            ft.Text(p["description"], size=11, color=ft.Colors.GREY_500),
                            ft.Container(height=4),
                            ft.Row([
                                ft.Text(f"✓ {completed_takes}", size=11, color=ft.Colors.GREEN_600),
                                ft.Text("•", size=11, color=ft.Colors.GREY_400),
                                ft.Text(f"⏳ {remaining_takes} left", size=11, color=ft.Colors.ORANGE_600),
                                ft.Text("•", size=11, color=ft.Colors.GREY_400),
                                ft.Text(f"🗓️ {start_date_display}", size=11, color=ft.Colors.PURPLE_600),
                                ft.Text("•", size=11, color=ft.Colors.GREY_400),
                                ft.Text(f"📅 {last_day_str}", size=11, color=ft.Colors.BLUE_600),
                            ], spacing=4),
                        ], expand=True, spacing=2),
                        # Scheduled times
                        ft.Column([
                            ft.Text(times_str, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_500, text_align=ft.TextAlign.RIGHT),
                            ft.Text(category_name, size=10, color=ft.Colors.GREY_500, text_align=ft.TextAlign.RIGHT),
                        ], horizontal_alignment=ft.CrossAxisAlignment.END),
                        ft.VerticalDivider(width=1, color=ft.Colors.GREY_300),
                        # Action buttons
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.Icons.TOGGLE_ON if p.get("active", True) else ft.icons.Icons.TOGGLE_OFF,
                                icon_color=ft.Colors.GREEN_600 if p.get("active", True) else ft.Colors.GREY_400,
                                icon_size=20,
                                tooltip="Disable" if p.get("active", True) else "Enable",
                                on_click=lambda e, pid=p["id"]: _toggle_pill(e, pid)
                            ),
                            ft.IconButton(
                                icon=ft.icons.Icons.EDIT,
                                icon_size=20,
                                icon_color=ft.Colors.GREY_500,
                                on_click=lambda e, p_data=p: _edit_pill(e, p_data)
                            ),
                            ft.IconButton(
                                icon=ft.icons.Icons.DELETE,
                                icon_color=ft.Colors.RED_300,
                                icon_size=20,
                                on_click=lambda e, pid=p["id"]: _delete_pill(e, pid)
                            ),
                        ], spacing=0),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=12,
                    bgcolor=ft.Colors.GREY_100,
                ),
                margin=ft.Margin.only(bottom=8),
            )
            controls.append(row)

        return controls

    pills_column = ft.Column(render_pills(), scroll=ft.ScrollMode.AUTO, expand=True)

    def go_to_timeline(e):
        if page_ref:
            page_ref.views.clear()
            page_ref.views.append(create_timeline_view(page_ref))
            page_ref.title = "📅 Daily Timeline"
            page_ref.update()

    def go_to_categories(e):
        if page_ref:
            page_ref.views.clear()
            page_ref.views.append(create_categories_view(page_ref))
            page_ref.title = "🏷️ Categories"
            page_ref.update()

    view.controls = [
        gradient_header("⏰ Active Alarms"),
        ft.Container(
            content=ft.Column([
                ft.Container(height=10),
                ft.Row([
                    ft.FilledButton(
                        "Add",
                        icon=ft.icons.Icons.ADD,
                        on_click=lambda e: create_pill_form(page_ref) if page_ref else None
                    ),
                    ft.FilledButton(
                        "Categories",
                        icon=ft.icons.Icons.LABEL,
                        on_click=go_to_categories
                    ),
                    ft.FilledButton(
                        "Schedule",
                        icon=ft.icons.Icons.CALENDAR_TODAY,
                        on_click=go_to_timeline
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ft.Container(height=10),
                pills_column,
                ft.Container(height=10),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            padding=10,
            expand=True,
        ),
    ]

    return view


def _edit_pill(e, p_data):
    global page
    create_pill_form(page, p_data)


def _delete_pill(e, pid):
    global page
    dlg = ft.AlertDialog(
        title=ft.Text("Delete this alarm?"),
        content=ft.Text("This action cannot be undone."),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Delete", bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE,
                              on_click=lambda e: (_delete_confirmed(pid), page.pop_dialog())),
        ]
    )
    page.show_dialog(dlg)


def _delete_confirmed(pid):
    global page
    manager.delete_pill(pid)
    refresh_views(page)


def create_timeline_view(page_ref=None):
    view = ft.View("/timeline")

    def go_to_dashboard(e):
        if page_ref:
            page_ref.views.clear()
            page_ref.views.append(create_dashboard_view(page_ref))
            page_ref.title = "⏰ Active Alarms"
            page_ref.update()

    def render_timeline():
        now = datetime.now()
        pills = [p for p in manager.get_all() if p.get("active", True)]

        # Collect all doses
        items = []
        for p in pills:
            times = get_today_schedule(p)
            for t in times:
                items.append({"time": t, "pill": p})

        # Group by time
        from collections import defaultdict
        time_groups = defaultdict(list)
        for item in items:
            time_key = item["time"].strftime("%H:%M")
            time_groups[time_key].append(item)

        # Sort times
        sorted_times = sorted(time_groups.keys())

        controls = []
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        controls.append(ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text("00:00", size=12, color=ft.Colors.GREY_400),
                    width=60,
                ),
                ft.Container(height=1, bgcolor=ft.Colors.GREY_300, expand=True),
            ], spacing=10),
            margin=ft.Margin.only(left=20, right=20),
        ))
        prev_time = start_of_day
        current_time_shown = False

        for time_str in sorted_times:
            time_obj = datetime.strptime(time_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            group = time_groups[time_str]

            # Add current time indicator if needed
            if not current_time_shown and now < time_obj:
                # Add spacing from previous
                if prev_time:
                    diff_min = (now - prev_time).total_seconds() / 60
                    height = max(10, diff_min * TIMELINE_SCALE)
                    controls.append(ft.Container(height=height))

                # Add red line for current time
                controls.append(ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(now.strftime("%H:%M"), size=12, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
                            width=60,
                        ),
                        ft.Container(height=2, bgcolor=ft.Colors.RED, expand=True),
                    ], spacing=10),
                    margin=ft.Margin.only(left=20, right=20),
                ))
                controls.append(ft.Container(height=10))
                current_time_shown = True
                prev_time = now

            # Calculate spacing from previous
            if prev_time:
                diff_min = (time_obj - prev_time).total_seconds() / 60
                height = max(10, diff_min * TIMELINE_SCALE)
                controls.append(ft.Container(height=height))

            # Render pills at this time
            pill_containers = []

            for item in group:
                p = item["pill"]
                main_color, bg_color = CATEGORIES[p["category"]]

                pill_containers.append(ft.Container(
                    content=ft.Column([
                        ft.Text(p["name"], size=16, color=main_color, weight=ft.FontWeight.BOLD),
                        ft.Text(p.get("description", ""), size=12, color=ft.Colors.GREY_700),
                    ], horizontal_alignment=ft.CrossAxisAlignment.START, spacing=2),
                    padding=ft.Padding.all(10),
                    bgcolor=bg_color,
                    border_radius=8,
                    expand=True,
                ))

            # Show time on left, pills on right
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(time_obj.strftime("%H:%M"), size=14, weight=ft.FontWeight.BOLD),
                        width=60,
                    ),
                    ft.Row(pill_containers, spacing=8, expand=True),
                ], spacing=10),
                margin=ft.Margin.only(left=20, right=20),
            ))

            prev_time = time_obj

        # Add current time at the end if not shown yet
        if not current_time_shown:
            if prev_time:
                diff_min = (now - prev_time).total_seconds() / 60
                height = max(10, diff_min * TIMELINE_SCALE)
                controls.append(ft.Container(height=height))

            controls.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(now.strftime("%H:%M"), size=12, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
                        width=60,
                    ),
                    ft.Container(height=2, bgcolor=ft.Colors.RED, expand=True),
                ], spacing=10),
                margin=ft.Margin.only(left=20, right=20),
            ))
            prev_time = now

        # Extend timeline to end of day
        end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
        last_time = prev_time if prev_time else now
        if last_time < end_of_day:
            diff_min = (end_of_day - last_time).total_seconds() / 60
            controls.append(ft.Container(height=max(10, diff_min * TIMELINE_SCALE)))

        controls.append(ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text("23:59", size=12, color=ft.Colors.GREY_400),
                    width=60,
                ),
                ft.Container(height=1, bgcolor=ft.Colors.GREY_300, expand=True),
            ], spacing=10),
            margin=ft.Margin.only(left=20, right=20),
        ))
        controls.append(ft.Container(height=40))

        return controls

    timeline_column = ft.Column(render_timeline(), scroll=ft.ScrollMode.AUTO, expand=True)

    view.controls = [
        gradient_header("📅 Today's Schedule", leading=ft.IconButton(
            icon=ft.icons.Icons.ARROW_BACK,
            icon_color=ft.Colors.WHITE,
            on_click=go_to_dashboard,
        )),
        ft.Container(
            content=ft.Column([
                ft.Text(f"{datetime.now().strftime('%Y-%m-%d')}", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),
                timeline_column,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            padding=10,
            expand=True,
        ),
    ]

    return view


def create_categories_view(page_ref=None):
    view = ft.View("/categories")

    def go_to_dashboard(e):
        if page_ref:
            page_ref.views.clear()
            page_ref.views.append(create_dashboard_view(page_ref))
            page_ref.title = "⏰ Active Alarms"
            page_ref.update()

    # Store text fields for each category
    category_fields = {}

    def render_categories():
        categories = manager.get_categories()
        controls = []

        for key, name in categories.items():
            main_color, bg_color = CATEGORIES[key]

            # Create text field for editing
            name_field = ft.TextField(
                value=name,
                text_size=16,
                border_color=main_color,
                focused_border_color=main_color,
            )

            # Store reference to the field
            category_fields[key] = name_field

            card = ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        # Color indicator
                        ft.Container(
                            width=48,
                            height=48,
                            bgcolor=main_color,
                            border_radius=6,
                        ),
                        # Category info and edit
                        ft.Column([
                            name_field,
                        ], expand=True, spacing=4),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=8,
                    bgcolor=bg_color,
                ),
                margin=ft.Margin.only(bottom=6),
            )
            controls.append(card)

        return controls

    def save_all_categories(e):
        if not page_ref:
            return
        # Save all category names
        for key, field in category_fields.items():
            new_name = field.value.strip()
            if new_name:
                manager.update_category_name(key, new_name)

        # Show snackbar
        snack_bar = ft.SnackBar(content=ft.Text("Saved"), open=True)
        page_ref.overlay.append(snack_bar)
        page_ref.update()

        # Go back to dashboard
        page_ref.views.clear()
        page_ref.views.append(create_dashboard_view(page_ref))
        page_ref.title = "⏰ Active Alarms"
        page_ref.update()

    categories_column = ft.Column(render_categories(), scroll=ft.ScrollMode.AUTO, expand=True)

    view.controls = [
        gradient_header("🏷️ Manage Categories", leading=ft.IconButton(
            icon=ft.icons.Icons.ARROW_BACK,
            icon_color=ft.Colors.WHITE,
            on_click=go_to_dashboard,
        )),
        ft.Container(
            content=ft.Column([
                ft.Container(height=10),
                ft.FilledButton(
                    "Save All",
                    icon=ft.icons.Icons.SAVE,
                    on_click=save_all_categories
                ),
                ft.Container(height=10),
                categories_column,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            padding=10,
            expand=True,
        ),
    ]

    return view


# ================= APP INITIALIZATION =================
alarm_audio = None


def main(p: ft.Page):
    global manager, page, alarm_audio
    manager = PillManager(STORAGE_FILE)
    page = p

    page.title = "AlarmPill"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 360
    page.window_height = 640
    page.window_min_width = 320

    if page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
        page.window.full_screen = True
        alarm_audio = fta.Audio(
            src="/alarm.wav",
            autoplay=False,
            volume=1.0,
            release_mode=fta.ReleaseMode.LOOP,
        )
        page.services.append(alarm_audio)

    def on_route_change(e):
        page.views.clear()

        # Add views based on route
        if page.route == "/timeline":
            page.views.append(create_timeline_view(page))
            page.title = "📅 Daily Timeline"
        elif page.route == "/categories":
            page.views.append(create_dashboard_view(page))
            page.views.append(create_categories_view(page))
            page.title = "🏷️ Categories"
        else:
            page.views.append(create_dashboard_view(page))
            page.title = "⏰ Active Alarms"

        page.update()

    def on_view_pop(e):
        page.go("/")

    page.on_route_change = on_route_change
    page.on_view_pop = on_view_pop
    page.route = "/"
    on_route_change(None)

    # Start background alarm checker
    asyncio.create_task(alarm_loop(page, manager))
    page.update()


if __name__ == "__main__":
    ft.run(main)
