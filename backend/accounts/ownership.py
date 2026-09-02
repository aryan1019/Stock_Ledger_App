"""
Ownership enforced at the queryset level.

Views never filter by user themselves. They call `Model.objects.owned_by(user)`,
so a forgotten filter fails CLOSED (empty queryset) rather than leaking rows.
"""

from django.db import models


class OwnedQuerySet(models.QuerySet):
    def owned_by(self, user):
        if user is None or not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(user=user)


class OwnedManager(models.Manager.from_queryset(OwnedQuerySet)):
    pass
