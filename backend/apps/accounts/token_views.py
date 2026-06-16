"""Safe JWT refresh view.

Wraps SimpleJWT's ``TokenRefreshView`` so that a refresh token referencing
a user that no longer exists in the database returns **401 Unauthorized**
instead of bubbling ``Account.DoesNotExist`` up as a **500 Server Error**.

Common trigger: a developer wipes/reseeds the demo accounts while a
browser still holds a refresh token tied to the old user_id.
"""

from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.views import TokenRefreshView


class SafeTokenRefreshView(TokenRefreshView):
    """Identical to ``TokenRefreshView`` but converts ``DoesNotExist``
    raised inside the SimpleJWT serializer to a clean 401 response.
    """

    def post(self, request, *args, **kwargs):
        from django.core.exceptions import ObjectDoesNotExist

        try:
            return super().post(request, *args, **kwargs)
        except ObjectDoesNotExist as exc:
            raise AuthenticationFailed(
                "User for this refresh token no longer exists.",
                code="user_not_found",
            ) from exc
