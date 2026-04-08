"""
Tests for the /health/ endpoint (Step 24).
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthCheck:
    """GET /health/ returns {"status": "ok"} without authentication."""

    def test_returns_ok_status(self):
        client = Client()
        response = client.get("/health/")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_no_authentication_required(self):
        """Health check must be accessible without any credentials."""
        client = Client()
        response = client.get("/health/")

        assert response.status_code == 200
