"""
Branch & Room models.

Database schema: README Section 14.3.

Tables defined here:
    - branches
    - room_types
    - rooms
    - room_images

Room statuses (README Section 5 & 19):
    available → booked → occupied → cleaning → ready
"""

from django.db import models


class Branch(models.Model):
    """
    Hostel branch / location.

    Fields per README:
        - id, name, location, is_active
    """

    name = models.CharField(max_length=255)
    location = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branches"
        ordering = ["name"]
        verbose_name = "Branch"
        verbose_name_plural = "Branches"

    def __str__(self):
        return self.name


class RoomType(models.Model):
    """
    Room type classification.

    Fields per README:
        - id, name
    """

    name = models.CharField(max_length=100)

    class Meta:
        db_table = "room_types"
        verbose_name = "Room Type"
        verbose_name_plural = "Room Types"

    def __str__(self):
        return self.name


class Room(models.Model):
    """
    Individual room within a branch.

    Fields per README:
        - id, branch_id (FK), room_type_id (FK), room_number,
          status, is_active
    """

    class RoomStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        BOOKED = "booked", "Booked"
        OCCUPIED = "occupied", "Occupied"
        CLEANING = "cleaning", "Cleaning"
        READY = "ready", "Ready"

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="rooms",
    )
    room_number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.AVAILABLE,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rooms"
        unique_together = ("branch", "room_number")
        verbose_name = "Room"
        verbose_name_plural = "Rooms"

    def __str__(self):
        return f"Room {self.room_number} ({self.branch.name})"


class RoomImage(models.Model):
    """
    Room gallery image (stored in Azure Blob Storage).

    Fields per README:
        - id, room_id (FK), image_url, is_primary, display_order, uploaded_at
    """

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image_url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "room_images"
        ordering = ["display_order"]
        verbose_name = "Room Image"
        verbose_name_plural = "Room Images"

    def __str__(self):
        return f"Image for Room {self.room.room_number}"
