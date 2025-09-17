
from django.contrib import admin
from .models import Restaurant, Order, Dish, OrderItem

admin.site.register(Restaurant)
admin.site.register(OrderItem)

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'restaurant', 'id')
    search_fields = ('name',)
    list_filter = ('restaurant', 'name')
    # actions = ("import_csv",)

class DishOrderItemInline(admin.TabularInline):
    model = OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("__str__", "id", "status")
    inlines = (DishOrderItemInline,)