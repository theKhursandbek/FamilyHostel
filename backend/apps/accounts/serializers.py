"""
Accounts serializers.

Serializers for Account and all role tables (README Section 14.1, 14.2).
"""

from rest_framework import serializers

from .models import Account, Administrator, Client, Director, Staff, SuperAdmin


class AccountSerializer(serializers.ModelSerializer):
    """Read-only account representation with computed roles."""

    roles = serializers.ListField(source="roles", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "telegram_id",
            "phone",
            "is_active",
            "roles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "account", "full_name", "created_at"]
        read_only_fields = ["id", "created_at"]


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ["id", "account", "branch", "full_name", "hire_date", "is_active"]
        read_only_fields = ["id"]


class AdministratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Administrator
        fields = ["id", "account", "branch", "full_name", "is_active"]
        read_only_fields = ["id"]


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ["id", "account", "branch", "full_name", "salary", "is_active"]
        read_only_fields = ["id"]


class SuperAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuperAdmin
        fields = ["id", "account", "full_name"]
        read_only_fields = ["id"]
