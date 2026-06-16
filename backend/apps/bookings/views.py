"""
Admin-facing booking views (back-office) — README Section 17.

Permission Matrix:
    - List/Retrieve: Admin+ (Admin, Director, SuperAdmin)
    - Create/Update/Delete: Admin+ with branch enforcement
    - Custom actions (cancel, complete): Admin+
    - Filtering, searching, ordering: Admin+

The client-facing endpoints (Telegram Mini App) are in client_views.py.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrHigher

from .filters import BookingFilter
from .models import Booking
from .serializers import (
    BookingSerializer,
    CompleteBookingSerializer,
    WalkInBookingSerializer,
)
from .services import cancel_booking, complete_booking, create_walkin_booking


def enforce_branch_on_create(user, branch):
    """
    Ensure the user has authority to create bookings in the given branch.

    - SuperAdmins can create in any branch.
    - Admins / Directors can only create in their assigned branch.

    Args:
        user: The request user
        branch: The branch instance

    Returns:
        The validated branch

    Raises:
        ValidationError: If user lacks authority
    """
    is_superadmin = bool(getattr(user, "superadmin_profile", None))
    user_branch_id = None

    # Check admin/director/staff profiles
    for profile_attr in ["administrator_profile", "director_profile", "staff_profile"]:
        profile = getattr(user, profile_attr, None)
        if profile and profile.branch:
            user_branch_id = profile.branch_id
            break

    if not is_superadmin and user_branch_id and user_branch_id != branch.id:
        raise ValidationError(
            {
                "branch": (
                    "You can only create bookings in your assigned branch. "
                    f"You are assigned to branch {user_branch_id}, "
                    f"but tried to create in branch {branch.id}."
                )
            }
        )

    return branch


class BookingViewSet(viewsets.ModelViewSet):
    """CRUD for bookings — Admin panel (back-office) only.

    Permissions:
        - Requires IsAuthenticated + IsAdminOrHigher
        - See permission matrix in docstring above

    Filters:
        - status: pending, paid, completed, canceled
        - branch: branch_id
        - check_in_after: YYYY-MM-DD
        - check_in_before: YYYY-MM-DD
        - check_out_after: YYYY-MM-DD
        - check_out_before: YYYY-MM-DD
        - room: room_id
        - client: client_id

    Ordering:
        - created_at (default: -created_at)
        - check_in_date
        - check_out_date
        - final_price
        - status

    Searching:
        - client__full_name
        - room__room_number
    """

    queryset = Booking.objects.select_related(
        "client", "room", "room__branch", "branch",
    ).prefetch_related("extensions")
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_class = BookingFilter
    ordering_fields = ["check_in_date", "check_out_date", "final_price", "status", "created_at"]
    ordering = ["-created_at"]
    search_fields = ["client__full_name", "room__room_number"]

    def get_queryset(self):
        """Optionally filter by branch for non-superadmin users."""
        qs = super().get_queryset()

        # Non-superadmins only see their own branch's bookings
        is_superadmin = bool(getattr(self.request.user, "superadmin_profile", None))
        if not is_superadmin:
            for profile_attr in [
                "administrator_profile",
                "director_profile",
                "staff_profile",
            ]:
                profile = getattr(self.request.user, profile_attr, None)
                if profile and profile.branch:
                    qs = qs.filter(branch_id=profile.branch_id)
                    break

        return qs

    def get_serializer_class(self):
        """Use specialized serializers for certain actions."""
        if self.action == "walk_in":
            return WalkInBookingSerializer
        if self.action in ["complete", "checkout"]:
            return CompleteBookingSerializer
        return BookingSerializer

    def perform_create(self, serializer):
        """Validate and create a booking (CRUD POST)."""
        serializer.save()

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /bookings/bookings/{pk}/cancel/ — Cancel a pending booking.

        Transitions: pending → canceled or paid → canceled
        Room status: booked → available
        """
        booking = self.get_object()
        try:
            booking = cancel_booking(booking, performed_by=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        serializer = BookingSerializer(booking)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="complete",
        serializer_class=CompleteBookingSerializer,
    )
    def complete(self, request, pk=None):
        """POST /bookings/bookings/{pk}/complete/ — Complete a paid booking (checkout).

        Transitions: paid → completed
        Room status: booked → cleaning (triggers cleaning task auto-creation)
        """
        return self._do_checkout(request, pk)

    @action(
        detail=True,
        methods=["post"],
        url_path="checkout",
        serializer_class=CompleteBookingSerializer,
    )
    def checkout(self, request, pk=None):
        """POST /bookings/bookings/{pk}/checkout/ — Alias for ``complete``.

        Modern endpoint name for completing a paid booking.
        """
        return self._do_checkout(request, pk)

    def _do_checkout(self, request, pk):
        """Shared logic for complete and checkout actions."""
        booking = self.get_object()
        # We accept the legacy ``refund_amount`` body field but ignore it;
        # validating the serializer keeps API responses consistent.
        serializer = CompleteBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = complete_booking(
                booking,
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        return Response(BookingSerializer(booking).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="walk-in",
        serializer_class=WalkInBookingSerializer,
    )
    def walk_in(self, request):
        """POST /bookings/bookings/walk-in/ — Create a new guest + first booking.

        Admin panel uses this to create a walk-in guest and their initial
        booking in one atomic operation. The guest account is created on-the-fly
        if it doesn't exist.

        Request body:
            {
                "full_name": "John Doe",
                "phone": "+998...",
                "passport_number": "AA123456",
                "room": <room_id>,
                "branch": <branch_id>,
                "check_in_date": "YYYY-MM-DD",
                "check_out_date": "YYYY-MM-DD",
                "price_at_booking": "500000.00",
                "discount_amount": "0.00" (optional)
            }

        Returns:
            201 Created with full booking details.
        """
        serializer = WalkInBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Get room and branch
        try:
            from apps.branches.models import Room, Branch
            room = Room.objects.get(pk=data["room"])
            branch = Branch.objects.get(pk=data["branch"])
        except (Room.DoesNotExist, Branch.DoesNotExist):
            raise ValidationError({"detail": "Invalid room or branch."})

        # Enforce branch authority
        branch = enforce_branch_on_create(request.user, branch)

        # Price is authoritative on the Room (set at room-creation time).
        # Allow an explicit override only if the caller really sent one.
        price = data.get("price_at_booking") or room.base_price

        try:
            booking = create_walkin_booking(
                full_name=data["full_name"],
                phone=data["phone"],
                passport_number=data["passport_number"],
                room=room,
                branch=branch,
                check_in_date=data["check_in_date"],
                check_out_date=data["check_out_date"],
                price_at_booking=price,
                discount_amount=data.get("discount_amount") or 0,
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            # Service layer raises django.core.exceptions.ValidationError —
            # surface it as a clean DRF 400 instead of a generic 500.
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )
