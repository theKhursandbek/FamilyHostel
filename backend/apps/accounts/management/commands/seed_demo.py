"""seed_demo — generate a rich, deterministic demo dataset.

Spec (Apr 2026):
    * 6 branches
    * Each branch: 1 director + 2 administrators + 3 staff
    * ~5 rooms per branch (2 room types)
    * Bookings (paid/pending/canceled) + Payments + Cleaning tasks
    * Cash sessions (day/night) with variance, some pending review
    * Shift assignments + attendance for staff/admins
    * Penalties, Salary adjustments, Facility logs (mixed states)
    * Salary records (advance + final) with audit log
    * Monthly report per branch for previous month

The command is **idempotent-ish**: it skips creating a branch if a
branch with the same demo name already exists. Pass --reset to wipe
all rows from the demo tables first (DOES NOT TOUCH SuperAdmins).

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --reset
"""

from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import (
    Account,
    Administrator,
    Client,
    Director,
    Staff,
)
from apps.admin_panel.models import CashSession, SystemSettings
from apps.bookings.models import Booking
from apps.branches.models import Branch, Room, RoomType
from apps.cleaning.models import AIResult, CleaningTask
from apps.payments.models import Payment, SalaryAuditLog, SalaryRecord
from apps.reports.models import (
    AuditLog,
    FacilityLog,
    MonthlyReport,
    Notification,
    Penalty,
    SalaryAdjustment,
)
from apps.staff.models import Attendance, DayOffRequest, ShiftAssignment

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

BRANCH_BLUEPRINTS = [
    ("Chilonzor", "Chilonzor district, Tashkent"),
    ("Yunusobod", "Yunusobod district, Tashkent"),
    ("Mirzo Ulugbek", "Mirzo Ulugbek district, Tashkent"),
    ("Sergeli", "Sergeli district, Tashkent"),
    ("Yashnobod", "Yashnobod district, Tashkent"),
    ("Olmazor", "Olmazor district, Tashkent"),
]

DIRECTOR_NAMES = [
    "Aziz Karimov",
    "Sevara Nazarova",
    "Bobur Yusupov",
    "Dilshod Rahimov",
    "Nodira Tursunova",
    "Sherzod Tashkentov",
]

ADMIN_NAMES = [
    "Jasur Tashpulatov", "Madina Salimova",
    "Otabek Nurmatov", "Gulnora Ergasheva",
    "Sherzod Mamatov", "Zarina Akhmedova",
    "Ravshan Khoshimov", "Kamola Yusupova",
    "Sardor Aliyev", "Iroda Shukurova",
    "Bekzod Kuziev", "Munisa Tojiyeva",
]

STAFF_NAMES = [
    "Aziza Komilova", "Shahnoza Ergasheva", "Malika Yo'ldosheva",
    "Dilfuza Ortikova", "Nigora Saidova", "Mohira Ismoilova",
    "Sevinch Pulatova", "Charos Ibragimova", "Diyora Toshmatova",
    "Madina Nazirova", "Ozoda Mahmudova", "Shoira Mirzayeva",
    "Yulduz Karimova", "Zilola Saidaliyeva", "Mehri Yusupova",
    "Nilufar Khasanova", "Fotima Otaboyeva", "Lola Ahmadjonova",
]

CLIENT_NAMES = [
    "Anvar Mahmudov", "Khurshid Latipov", "Rustam Tursunov",
    "Bobur Saidov", "Jamshid Rakhimov", "Akmal Yusupov",
    "Furkat Karimov", "Davlat Komilov", "Olim Nazirov",
    "Sanjar Hakimov", "Temur Boltayev", "Ulugbek Sharipov",
    "Kamron Yo'lchiyev", "Murodjon Aliyev", "Otabek Sodikov",
    "Ravshan Tojiyev", "Shokhrukh Pulatov", "Umid Toshpo'latov",
    "Vali Mirzayev", "Yorqin Saidov", "Asror Khoshimov",
    "Botir Komilov", "Doniyor Nuriddinov", "Eldor Murodov",
]

ROOM_TYPE_NAMES = ["Standard", "Premium"]

FACILITY_DESCRIPTIONS = {
    "products": [
        "Weekly grocery run — bread, eggs, milk, tea",
        "Bottled water restock",
        "Coffee + sugar refill for guest lobby",
    ],
    "detergents": [
        "Floor cleaner + bleach restock",
        "Laundry detergent for staff washer",
        "Glass cleaner + mop heads",
    ],
    "telecom": [
        "Monthly internet bill (UzTelecom)",
        "Mobile top-up for branch SIM",
    ],
    "repair": [
        "Plumber — Room 102 leaking faucet",
        "Electrician — corridor light fixture",
        "Boiler service — annual inspection",
    ],
    "utilities": [
        "Gas bill (Hududgaz)",
        "Electricity bill",
        "Water + sewage bill",
    ],
    "other": [
        "Towel replacement set",
        "Stationery + receipt paper",
    ],
}

PENALTY_REASONS = [
    "Arrived 45 minutes late to shift",
    "Skipped check-in confirmation for room 204",
    "Failed to log cash variance at handover",
    "Did not follow cleaning checklist",
    "Unexcused absence on scheduled shift",
]

ADJUSTMENT_REASONS_BONUS = [
    "Outstanding guest review — 5 stars from VIP guest",
    "Covered weekend shift on short notice",
    "Spotless surprise inspection",
]
ADJUSTMENT_REASONS_PENALTY = [
    "Cash variance penalty (deducted)",
    "Late arrival x3 in one week",
    "Missed mandatory training",
]

# ---------------------------------------------------------------------------
# Demo telegram-id range (negative, well outside real Telegram IDs)
# ---------------------------------------------------------------------------

DEMO_TG_BASE = -900_000_000
DEMO_PASSWORD = "demo1234"  # uniform dev login for every seeded role account


def _next_tg_id(start: int, n: int) -> int:
    return DEMO_TG_BASE - start - n


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Generate a comprehensive demo dataset (6 branches, full month of activity)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Wipe all rows from demo tables before seeding (keeps SuperAdmins).",
        )
        parser.add_argument(
            "--seed", type=int, default=42,
            help="Random seed for deterministic output.",
        )
        parser.add_argument(
            "--days", type=int, default=59,
            help="How many days back from today to span (default 59 = ~2 months).",
        )

    def handle(self, *args, **opts):
        self.rng = random.Random(opts["seed"])
        self.span_days = opts["days"]
        self.today = dt.date.today()
        self.start_date = self.today - dt.timedelta(days=self.span_days)

        with transaction.atomic():
            if opts["reset"]:
                self._reset()
            self._ensure_settings()
            room_types = self._ensure_room_types()
            branches = self._create_branches()
            for idx, branch in enumerate(branches):
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f"\n=== Seeding {branch.name} ({idx + 1}/{len(branches)}) ==="
                ))
                self._seed_branch(branch, idx, room_types)

            self.stdout.write(self.style.SUCCESS("\n[OK] Seed complete."))
            self._print_summary()

    # ------------------------------------------------------------------
    # RESET
    # ------------------------------------------------------------------

    def _reset(self):
        self.stdout.write(self.style.WARNING("Wiping demo data…"))
        # Order matters: children before parents.
        for model in (
            SalaryAuditLog, SalaryRecord, SalaryAdjustment, Notification,
            Penalty, AuditLog, FacilityLog, MonthlyReport,
            Attendance, ShiftAssignment, DayOffRequest,
            CashSession, AIResult, CleaningTask,
            Payment, Booking,
            Client, Staff, Administrator, Director,
            Room, RoomType, Branch,
        ):
            n = model.objects.all().count()
            model.objects.all().delete()
            self.stdout.write(f"  - cleared {model.__name__}: {n}")

        # Wipe demo accounts. Crucially, EXCLUDE accounts that own a
        # SuperAdmin profile — ``create_superadmin`` also uses negative
        # synthetic telegram_ids, so a naive `telegram_id__lt=0` filter
        # would nuke the CEO. We protect both by profile and by Account.pk.
        protected_pks = list(
            Account.objects.filter(superadmin_profile__isnull=False)
            .values_list("pk", flat=True)
        )
        deleted_accs = (
            Account.objects
            .filter(telegram_id__lt=0)
            .exclude(pk__in=protected_pks)
            .delete()
        )
        self.stdout.write(
            f"  - cleared demo Accounts: {deleted_accs[0]} "
            f"(protected SuperAdmin Accounts: {len(protected_pks)})"
        )

    # ------------------------------------------------------------------
    # CORE SEEDS
    # ------------------------------------------------------------------

    def _ensure_settings(self):
        SystemSettings.objects.get_or_create(
            pk=1,
            defaults=dict(
                salary_mode=SystemSettings.SalaryMode.SHIFT,
                salary_cycle=SystemSettings.SalaryCycle.MONTHLY,
                staff_shift_rate=Decimal("100000"),
                per_room_rate=Decimal("15000"),
                director_fixed_salary=Decimal("2000000"),
                admin_shift_rate=Decimal("150000"),
            ),
        )

    def _ensure_room_types(self):
        types = []
        for name in ROOM_TYPE_NAMES:
            t, _ = RoomType.objects.get_or_create(name=name)
            types.append(t)
        return types

    def _create_branches(self):
        branches = []
        for name, location in BRANCH_BLUEPRINTS:
            b, created = Branch.objects.get_or_create(
                name=name,
                defaults=dict(
                    location=location,
                    is_active=True,
                    working_days_per_month=26,
                    monthly_expense_limit=Decimal("5000000"),
                ),
            )
            branches.append(b)
            tag = "created" if created else "exists"
            self.stdout.write(f"  branch {tag}: {b.name}")
        return branches

    # ------------------------------------------------------------------
    # PER-BRANCH SEEDING
    # ------------------------------------------------------------------

    def _seed_branch(self, branch: Branch, idx: int, room_types):
        director = self._make_director(branch, idx)
        admins = self._make_admins(branch, idx)
        staffs = self._make_staff(branch, idx)
        rooms = self._make_rooms(branch, room_types)
        clients = self._make_clients(branch, idx)
        bookings = self._make_bookings(branch, rooms, clients, admins)
        self._make_payments(bookings, admins)
        self._make_cleaning_tasks(bookings, staffs, branch)
        self._make_cash_sessions(branch, admins, director)
        self._make_shifts_and_attendance(branch, director, admins, staffs)
        self._make_penalties(branch, director, admins, staffs)
        self._make_salary_adjustments(branch, director, admins, staffs)
        self._make_facility_logs(branch, director)
        self._make_salary_records(director, admins, staffs)
        self._make_monthly_report(branch, director)
        self._make_notifications(director, admins, staffs)
        self._make_audit_log_entries(director, admins, staffs)

    # ------------------------------------------------------------------
    # PEOPLE
    # ------------------------------------------------------------------

    def _make_director(self, branch: Branch, idx: int) -> Director:
        name = DIRECTOR_NAMES[idx % len(DIRECTOR_NAMES)]
        tg = _next_tg_id(idx * 1000, 1)
        phone = f"+99890{idx + 1}000001"
        acc, _ = Account.objects.get_or_create(
            telegram_id=tg,
            defaults=dict(phone=phone, is_active=True),
        )
        # Always (re)apply phone + password so re-seeds stay in sync.
        acc.phone = phone
        acc.set_password(DEMO_PASSWORD)
        acc.save(update_fields=["phone", "password"])
        director, _ = Director.objects.get_or_create(
            account=acc,
            defaults=dict(
                branch=branch,
                full_name=name,
                is_active=True,
            ),
        )
        return director

    def _make_admins(self, branch: Branch, idx: int) -> list[Administrator]:
        admins = []
        for i in range(2):
            name = ADMIN_NAMES[(idx * 2 + i) % len(ADMIN_NAMES)]
            tg = _next_tg_id(idx * 1000, 10 + i)
            phone = f"+99890{idx + 1}0{i + 1:02d}001"
            acc, _ = Account.objects.get_or_create(
                telegram_id=tg,
                defaults=dict(phone=phone, is_active=True),
            )
            acc.phone = phone
            acc.set_password(DEMO_PASSWORD)
            acc.save(update_fields=["phone", "password"])
            adm, _ = Administrator.objects.get_or_create(
                account=acc,
                defaults=dict(branch=branch, full_name=name, is_active=True),
            )
            admins.append(adm)
        return admins

    def _make_staff(self, branch: Branch, idx: int) -> list[Staff]:
        staffs = []
        for i in range(3):
            name = STAFF_NAMES[(idx * 3 + i) % len(STAFF_NAMES)]
            tg = _next_tg_id(idx * 1000, 20 + i)
            phone = f"+99890{idx + 1}0{i + 1:02d}100"
            acc, _ = Account.objects.get_or_create(
                telegram_id=tg,
                defaults=dict(phone=phone, is_active=True),
            )
            acc.phone = phone
            acc.set_password(DEMO_PASSWORD)
            acc.save(update_fields=["phone", "password"])
            s, _ = Staff.objects.get_or_create(
                account=acc,
                defaults=dict(
                    branch=branch, full_name=name,
                    hire_date=self.today - dt.timedelta(days=180 + i * 30),
                    is_active=True,
                ),
            )
            staffs.append(s)
        return staffs

    def _make_clients(self, branch: Branch, idx: int) -> list[Client]:
        clients = []
        for i in range(8):
            name = CLIENT_NAMES[(idx * 4 + i) % len(CLIENT_NAMES)]
            tg = _next_tg_id(idx * 1000, 100 + i)
            acc, _ = Account.objects.get_or_create(
                telegram_id=tg,
                defaults=dict(phone=f"+99893{idx:02d}0{i:03d}", is_active=True),
            )
            c, _ = Client.objects.get_or_create(
                account=acc,
                defaults=dict(
                    full_name=name,
                    passport_number=f"AA{idx:02d}{i:04d}{self.rng.randint(10, 99)}",
                ),
            )
            clients.append(c)
        return clients

    # ------------------------------------------------------------------
    # ROOMS
    # ------------------------------------------------------------------

    def _make_rooms(self, branch: Branch, room_types):
        rooms = []
        # 5 rooms per branch — 3 standard, 2 premium
        plan = [(101, room_types[0]), (102, room_types[0]), (103, room_types[0]),
                (201, room_types[1]), (202, room_types[1])]
        for number, rt in plan:
            base = Decimal("250000") if rt.name == "Standard" else Decimal("450000")
            r, _ = Room.objects.get_or_create(
                branch=branch, room_number=str(number),
                defaults=dict(
                    room_type=rt, base_price=base,
                    status=Room.RoomStatus.AVAILABLE, is_active=True,
                ),
            )
            rooms.append(r)
        return rooms

    # ------------------------------------------------------------------
    # BOOKINGS + PAYMENTS
    # ------------------------------------------------------------------

    def _make_bookings(self, branch, rooms, clients, admins) -> list[Booking]:
        bookings = []
        # Create ~ 40 bookings per branch over the date range.
        for _ in range(40):
            client = self.rng.choice(clients)
            room = self.rng.choice(rooms)
            check_in = self.start_date + dt.timedelta(
                days=self.rng.randint(0, max(self.span_days - 4, 1))
            )
            nights = self.rng.choice([1, 1, 2, 2, 3, 4, 5])
            check_out = check_in + dt.timedelta(days=nights)
            price = room.base_price * nights
            discount = Decimal(self.rng.choice([0, 0, 0, 10000, 20000, 50000]))
            final_price = price - discount

            # Status mix: 70% paid, 20% pending, 10% canceled
            roll = self.rng.random()
            if roll < 0.7:
                status = Booking.BookingStatus.PAID
            elif roll < 0.9:
                status = Booking.BookingStatus.PENDING
            else:
                status = Booking.BookingStatus.CANCELED

            source = self.rng.choice([
                Booking.BookingSource.MANUAL,
                Booking.BookingSource.MANUAL,
                Booking.BookingSource.MANUAL,
                Booking.BookingSource.TELEGRAM,
            ])

            b = Booking.objects.create(
                client=client, room=room, branch=branch,
                check_in_date=check_in, check_out_date=check_out,
                price_at_booking=price, discount_amount=discount,
                final_price=final_price, status=status, source=source,
            )
            bookings.append(b)
        self.stdout.write(f"  bookings: {len(bookings)}")
        return bookings

    def _make_payments(self, bookings, admins):
        n = 0
        for b in bookings:
            if b.status != Booking.BookingStatus.PAID:
                # ~50% of pending also have a partial payment recorded.
                if b.status == Booking.BookingStatus.PENDING and self.rng.random() < 0.5:
                    half = (b.final_price / 2).quantize(Decimal("1.00"))
                    Payment.objects.create(
                        booking=b, amount=half,
                        payment_type=Payment.PaymentType.MANUAL,
                        method=self.rng.choice([
                            Payment.PaymentMethod.CASH,
                            Payment.PaymentMethod.TERMINAL,
                            Payment.PaymentMethod.QR,
                        ]),
                        is_paid=True,
                        paid_at=timezone.make_aware(dt.datetime.combine(
                            b.check_in_date, dt.time(self.rng.randint(9, 18), 0)
                        )),
                        created_by=self.rng.choice(admins),
                    )
                    n += 1
                continue
            Payment.objects.create(
                booking=b, amount=b.final_price,
                payment_type=Payment.PaymentType.MANUAL,
                method=self.rng.choice([
                    Payment.PaymentMethod.CASH,
                    Payment.PaymentMethod.TERMINAL,
                    Payment.PaymentMethod.QR,
                    Payment.PaymentMethod.CARD_TRANSFER,
                ]),
                is_paid=True,
                paid_at=timezone.make_aware(dt.datetime.combine(
                    b.check_in_date, dt.time(self.rng.randint(9, 18), 0)
                )),
                created_by=self.rng.choice(admins),
            )
            n += 1
        self.stdout.write(f"  payments: {n}")

    # ------------------------------------------------------------------
    # CLEANING
    # ------------------------------------------------------------------

    def _make_cleaning_tasks(self, bookings, staffs, branch):
        n = 0
        # Process bookings whose checkout already happened.
        seen_active_room = set()
        for b in bookings:
            if b.status == Booking.BookingStatus.CANCELED:
                continue
            if b.check_out_date > self.today:
                continue
            assigned = self.rng.choice(staffs)
            # 80% completed, 15% pending, 5% in_progress.
            roll = self.rng.random()
            if roll < 0.8:
                status = CleaningTask.TaskStatus.COMPLETED
                completed_at = timezone.make_aware(dt.datetime.combine(
                    b.check_out_date, dt.time(self.rng.randint(11, 16), 0)
                ))
            elif roll < 0.95:
                status = CleaningTask.TaskStatus.PENDING
                completed_at = None
            else:
                status = CleaningTask.TaskStatus.IN_PROGRESS
                completed_at = None

            # Avoid violating unique active task per room.
            if status != CleaningTask.TaskStatus.COMPLETED:
                if b.room_id in seen_active_room:
                    status = CleaningTask.TaskStatus.COMPLETED
                    completed_at = timezone.make_aware(dt.datetime.combine(
                        b.check_out_date, dt.time(15, 0)
                    ))
                else:
                    seen_active_room.add(b.room_id)

            task = CleaningTask.objects.create(
                room=b.room, branch=branch, status=status,
                priority=self.rng.choice([
                    CleaningTask.Priority.LOW,
                    CleaningTask.Priority.NORMAL,
                    CleaningTask.Priority.NORMAL,
                    CleaningTask.Priority.HIGH,
                ]),
                assigned_to=assigned,
                completed_at=completed_at,
            )
            # AI result on ~half of completed tasks.
            if status == CleaningTask.TaskStatus.COMPLETED and self.rng.random() < 0.5:
                AIResult.objects.create(
                    task=task,
                    result=AIResult.Result.APPROVED if self.rng.random() < 0.85
                        else AIResult.Result.REJECTED,
                    feedback_text="Auto-validated by demo seeder.",
                    ai_model_version="demo-v1",
                )
            n += 1
        self.stdout.write(f"  cleaning tasks: {n}")

    # ------------------------------------------------------------------
    # CASH SESSIONS
    # ------------------------------------------------------------------

    def _make_cash_sessions(self, branch, admins, director):
        # 1 day + 1 night session per day for the last 30 days.
        n = 0
        for day_off in range(30):
            d = self.today - dt.timedelta(days=day_off + 1)
            for shift, admin in (
                (CashSession.ShiftType.DAY, admins[0]),
                (CashSession.ShiftType.NIGHT, admins[1]),
            ):
                opening = Decimal(self.rng.choice([100000, 200000, 500000]))
                closing = opening + Decimal(self.rng.randint(50, 5000) * 1000)
                difference = Decimal(self.rng.choice([0, 0, 0, -10000, 5000, -50000]))
                start_hour = 8 if shift == CashSession.ShiftType.DAY else 19
                end_hour = 19 if shift == CashSession.ShiftType.DAY else 8
                start_dt = timezone.make_aware(dt.datetime.combine(d, dt.time(start_hour, 0)))
                end_d = d if shift == CashSession.ShiftType.DAY else d + dt.timedelta(days=1)
                end_dt = timezone.make_aware(dt.datetime.combine(end_d, dt.time(end_hour, 0)))

                if abs(difference) > 5000:
                    note = "Cash variance flagged at handover"
                    var_status = self.rng.choice([
                        CashSession.VarianceStatus.PENDING,
                        CashSession.VarianceStatus.APPROVED,
                    ])
                else:
                    note = ""
                    var_status = CashSession.VarianceStatus.APPROVED

                CashSession.objects.create(
                    admin=admin, branch=branch, shift_type=shift,
                    start_time=start_dt, end_time=end_dt,
                    opening_balance=opening, closing_balance=closing,
                    difference=difference, note=note,
                    handed_over_to=admins[1] if admin == admins[0] else admins[0],
                    variance_status=var_status,
                    reviewed_by=director if var_status == CashSession.VarianceStatus.APPROVED and difference != 0 else None,
                    reviewed_at=end_dt if var_status == CashSession.VarianceStatus.APPROVED and difference != 0 else None,
                    review_comment="Reconciled with petty cash" if difference != 0 and var_status == CashSession.VarianceStatus.APPROVED else "",
                )
                n += 1
        self.stdout.write(f"  cash sessions: {n}")

    # ------------------------------------------------------------------
    # SHIFTS + ATTENDANCE
    # ------------------------------------------------------------------

    def _make_shifts_and_attendance(self, branch, director, admins, staffs):
        n_shifts = 0
        n_att = 0
        # Last 30 days, alternate admins between day/night, distribute staff.
        for day_off in range(30):
            d = self.today - dt.timedelta(days=day_off + 1)
            # Admins
            day_admin = admins[day_off % 2]
            night_admin = admins[(day_off + 1) % 2]
            for adm, shift in ((day_admin, ShiftAssignment.ShiftType.DAY),
                               (night_admin, ShiftAssignment.ShiftType.NIGHT)):
                ShiftAssignment.objects.get_or_create(
                    account=adm.account, role=ShiftAssignment.Role.ADMIN,
                    branch=branch, shift_type=shift, date=d,
                    defaults=dict(assigned_by=director),
                )
                n_shifts += 1
                self._record_attendance(adm.account, branch, d, shift)
                n_att += 1
            # Staff (cleaners) — assign 2 of 3 to day shift.
            for s in staffs[: 2]:
                ShiftAssignment.objects.get_or_create(
                    account=s.account, role=ShiftAssignment.Role.STAFF,
                    branch=branch, shift_type=ShiftAssignment.ShiftType.DAY, date=d,
                    defaults=dict(assigned_by=director),
                )
                n_shifts += 1
                self._record_attendance(s.account, branch, d,
                                        ShiftAssignment.ShiftType.DAY)
                n_att += 1
        self.stdout.write(f"  shifts: {n_shifts} | attendance: {n_att}")

    def _record_attendance(self, account, branch, d, shift):
        roll = self.rng.random()
        if roll < 0.85:
            status = Attendance.AttendanceStatus.PRESENT
        elif roll < 0.95:
            status = Attendance.AttendanceStatus.LATE
        else:
            status = Attendance.AttendanceStatus.ABSENT

        if status == Attendance.AttendanceStatus.ABSENT:
            check_in = check_out = None
        else:
            base = 8 if shift == ShiftAssignment.ShiftType.DAY else 19
            late_minutes = self.rng.randint(31, 50) if status == Attendance.AttendanceStatus.LATE else self.rng.randint(0, 10)
            ci = timezone.make_aware(dt.datetime.combine(
                d, dt.time(base, 0)
            )) + dt.timedelta(minutes=late_minutes)
            co = ci + dt.timedelta(hours=11)
            check_in, check_out = ci, co

        Attendance.objects.get_or_create(
            account=account, branch=branch, date=d, shift_type=shift,
            defaults=dict(check_in=check_in, check_out=check_out, status=status),
        )

    # ------------------------------------------------------------------
    # PENALTIES + SALARY ADJUSTMENTS
    # ------------------------------------------------------------------

    def _make_penalties(self, branch, director, admins, staffs):
        people = [a.account for a in admins] + [s.account for s in staffs]
        n = 0
        for _ in range(self.rng.randint(2, 4)):
            target = self.rng.choice(people)
            amount = Decimal(self.rng.choice([20000, 30000, 50000, 100000]))
            ptype = self.rng.choice([
                Penalty.PenaltyType.LATE,
                Penalty.PenaltyType.ABSENCE,
                None,  # free-form
            ])
            Penalty.objects.create(
                account=target, type=ptype, count=1,
                penalty_amount=amount,
                reason=self.rng.choice(PENALTY_REASONS),
                created_by=director.account,
            )
            n += 1
        self.stdout.write(f"  penalties: {n}")

    def _make_salary_adjustments(self, branch, director, admins, staffs):
        people = [a.account for a in admins] + [s.account for s in staffs]
        n = 0
        # Adjustments for current + previous month.
        for delta_month in (0, 1):
            ref = self.today.replace(day=1) - dt.timedelta(days=delta_month * 30)
            year, month = ref.year, ref.month
            for target in self.rng.sample(people, k=min(3, len(people))):
                if self.rng.random() < 0.5:
                    kind = SalaryAdjustment.Kind.BONUS_PLUS
                    amount = Decimal(self.rng.choice([50000, 100000, 150000]))
                    reason = self.rng.choice(ADJUSTMENT_REASONS_BONUS)
                else:
                    kind = SalaryAdjustment.Kind.PENALTY
                    amount = Decimal(self.rng.choice([20000, 50000, 80000]))
                    reason = self.rng.choice(ADJUSTMENT_REASONS_PENALTY)
                SalaryAdjustment.objects.create(
                    account=target, branch=branch,
                    year=year, month=month,
                    kind=kind, amount=amount, reason=reason,
                    created_by=director.account,
                )
                n += 1
        self.stdout.write(f"  salary adjustments: {n}")

    # ------------------------------------------------------------------
    # FACILITY LOGS
    # ------------------------------------------------------------------

    def _make_facility_logs(self, branch, director):
        n = 0
        sa = Account.objects.filter(superadmin_profile__isnull=False).first()
        super_admin_profile = getattr(sa, "superadmin_profile", None) if sa else None
        for _ in range(self.rng.randint(8, 12)):
            ftype = self.rng.choice(list(FACILITY_DESCRIPTIONS.keys()))
            cost = Decimal(self.rng.choice([
                50000, 100000, 200000, 350000, 500000, 750000, 1200000
            ]))
            roll = self.rng.random()
            if roll < 0.5:
                status = FacilityLog.LogStatus.PAID
                pm = self.rng.choice([FacilityLog.PaymentMethod.CASH,
                                       FacilityLog.PaymentMethod.CARD])
                approved_at = timezone.now() - dt.timedelta(days=self.rng.randint(1, 25))
                paid_at = approved_at + dt.timedelta(hours=self.rng.randint(1, 48))
            elif roll < 0.7:
                status = FacilityLog.LogStatus.APPROVED_CASH
                pm = FacilityLog.PaymentMethod.CASH
                approved_at = timezone.now() - dt.timedelta(days=self.rng.randint(1, 5))
                paid_at = None
            elif roll < 0.85:
                status = FacilityLog.LogStatus.PENDING
                pm = None
                approved_at = None
                paid_at = None
            else:
                status = FacilityLog.LogStatus.REJECTED
                pm = None
                approved_at = None
                paid_at = None

            log = FacilityLog.objects.create(
                branch=branch,
                requested_by=director.account,
                type=ftype,
                shift_type=self.rng.choice([
                    FacilityLog.ShiftType.DAY,
                    FacilityLog.ShiftType.NIGHT,
                    None,
                ]),
                description=self.rng.choice(FACILITY_DESCRIPTIONS[ftype]),
                cost=cost, status=status,
                payment_method=pm,
                approved_by=super_admin_profile if approved_at and super_admin_profile else None,
                approved_at=approved_at,
                approval_note="Approved per branch budget" if approved_at else "",
                paid_at=paid_at,
            )
            if status == FacilityLog.LogStatus.REJECTED and super_admin_profile:
                log.rejected_by = super_admin_profile
                log.rejected_at = timezone.now() - dt.timedelta(days=self.rng.randint(1, 5))
                log.rejection_reason = "Out of budget for the month"
                log.save(update_fields=["rejected_by", "rejected_at", "rejection_reason"])
            n += 1
        self.stdout.write(f"  facility logs: {n}")

    # ------------------------------------------------------------------
    # SALARY RECORDS  (advance + final, with audit log)
    # ------------------------------------------------------------------

    def _make_salary_records(self, director, admins, staffs):
        n = 0
        # Previous-month period (for FINAL records — already paid)
        prev = self.today.replace(day=1) - dt.timedelta(days=1)
        prev_start = prev.replace(day=1)
        prev_end = prev

        # Current-month period (for ADVANCE — paid mid-month; FINAL still pending)
        cur_start = self.today.replace(day=1)
        cur_end = self.today

        people = [director.account] + [a.account for a in admins] + [s.account for s in staffs]
        rng_amounts = {
            "director": Decimal("2000000"),
            "admin": Decimal("1800000"),
            "staff": Decimal("1200000"),
        }

        for acc in people:
            if acc == director.account:
                base = rng_amounts["director"]
            elif acc.is_administrator:
                base = rng_amounts["admin"]
            else:
                base = rng_amounts["staff"]

            # Previous month FINAL — paid
            rec_final, created = SalaryRecord.objects.get_or_create(
                account=acc, period_start=prev_start, period_end=prev_end,
                kind=SalaryRecord.SalaryKind.FINAL,
                defaults=dict(
                    amount=base,
                    status=SalaryRecord.SalaryStatus.PAID,
                ),
            )
            if created:
                SalaryAuditLog.objects.create(
                    record=rec_final, actor=None,
                    action=SalaryAuditLog.Action.CALCULATED,
                    after_amount=base, note="Locked by demo seeder",
                )
                SalaryAuditLog.objects.create(
                    record=rec_final, actor=director.account,
                    action=SalaryAuditLog.Action.MARKED_PAID,
                    after_amount=base, note="Paid via demo seeder",
                )
                n += 1

            # Current month ADVANCE — paid (assume we are past the 15th)
            adv_amount = (base / 2).quantize(Decimal("1.00"))
            rec_adv, created = SalaryRecord.objects.get_or_create(
                account=acc, period_start=cur_start, period_end=cur_end,
                kind=SalaryRecord.SalaryKind.ADVANCE,
                defaults=dict(
                    amount=adv_amount,
                    status=SalaryRecord.SalaryStatus.PAID,
                ),
            )
            if created:
                SalaryAuditLog.objects.create(
                    record=rec_adv, actor=director.account,
                    action=SalaryAuditLog.Action.MARKED_PAID,
                    after_amount=adv_amount, note="Mid-month advance (demo)",
                )
                n += 1
        self.stdout.write(f"  salary records: {n}")

    # ------------------------------------------------------------------
    # MONTHLY REPORT
    # ------------------------------------------------------------------

    def _make_monthly_report(self, branch, director):
        prev = self.today.replace(day=1) - dt.timedelta(days=1)
        MonthlyReport.objects.get_or_create(
            branch=branch, year=prev.year, month=prev.month,
            defaults=dict(
                created_by=director,
                summary_notes=(
                    f"Auto-generated demo summary for {prev.strftime('%B %Y')}. "
                    "Occupancy steady; one cash variance reconciled. "
                    "All staff paid on time."
                ),
            ),
        )

    # ------------------------------------------------------------------
    # NOTIFICATIONS + AUDIT LOGS
    # ------------------------------------------------------------------

    def _make_notifications(self, director, admins, staffs):
        targets = [director.account] + [a.account for a in admins] + [s.account for s in staffs]
        for acc in targets:
            for _ in range(self.rng.randint(2, 5)):
                ntype = self.rng.choice([
                    Notification.NotificationType.PAYMENT,
                    Notification.NotificationType.CLEANING,
                    Notification.NotificationType.SHIFT,
                    Notification.NotificationType.SYSTEM,
                ])
                Notification.objects.create(
                    account=acc, type=ntype,
                    message=f"[demo] {ntype.label} update",
                    is_read=self.rng.random() < 0.4,
                )

    def _make_audit_log_entries(self, director, admins, staffs):
        actors = [director.account] + [a.account for a in admins]
        for _ in range(self.rng.randint(5, 10)):
            actor = self.rng.choice(actors)
            AuditLog.objects.create(
                account=actor,
                role="director" if actor == director.account else "administrator",
                action=self.rng.choice([
                    "booking.create", "payment.mark_paid",
                    "cleaning.assign", "cash_session.close",
                    "facility_log.request",
                ]),
                entity_type=self.rng.choice([
                    "Booking", "Payment", "CleaningTask",
                    "CashSession", "FacilityLog",
                ]),
                entity_id=self.rng.randint(1, 200),
                before_data=None,
                after_data={"demo": True},
            )

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------

    def _print_summary(self):
        rows = [
            ("Branches", Branch.objects.count()),
            ("Directors", Director.objects.count()),
            ("Administrators", Administrator.objects.count()),
            ("Staff", Staff.objects.count()),
            ("Clients", Client.objects.count()),
            ("Rooms", Room.objects.count()),
            ("Bookings", Booking.objects.count()),
            ("Payments", Payment.objects.count()),
            ("Cleaning tasks", CleaningTask.objects.count()),
            ("Cash sessions", CashSession.objects.count()),
            ("Shift assignments", ShiftAssignment.objects.count()),
            ("Attendance", Attendance.objects.count()),
            ("Penalties", Penalty.objects.count()),
            ("Salary adjustments", SalaryAdjustment.objects.count()),
            ("Facility logs", FacilityLog.objects.count()),
            ("Salary records", SalaryRecord.objects.count()),
            ("Salary audit logs", SalaryAuditLog.objects.count()),
            ("Monthly reports", MonthlyReport.objects.count()),
            ("Notifications", Notification.objects.count()),
            ("Audit logs", AuditLog.objects.count()),
        ]
        self.stdout.write(self.style.MIGRATE_HEADING("\n— Final counts —"))
        for label, count in rows:
            self.stdout.write(f"  {label:<22} {count}")
