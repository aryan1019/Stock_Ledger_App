from django.contrib import admin

from .models import CorporateAction, PriceSnapshot, Stock

admin.site.register(Stock)
admin.site.register(CorporateAction)
admin.site.register(PriceSnapshot)
