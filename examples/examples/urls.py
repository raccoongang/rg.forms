"""URL configuration for examples app."""

from django.urls import path

from . import views

app_name = "examples"

urlpatterns = [
    path("", views.index, name="index"),
    path("risks/", views.risks, name="risks"),
    path("order/", views.order_form, name="order_form"),
    path("calculator/", views.price_calculator, name="price_calculator"),
    path("contact/", views.contact_form, name="contact_form"),
    path("cascading/", views.cascading_form, name="cascading_form"),
    path("backend-validation/", views.backend_validation, name="backend_validation"),
    path("conditional-attributes/", views.conditional_attributes, name="conditional_attributes"),
    path("field-groups/", views.field_groups, name="field_groups"),
    path("sse-validation/", views.sse_validation, name="sse_validation"),
]
