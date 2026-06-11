from django.urls import path

from app.pages.sites import views

urlpatterns = [
    path("sites/<int:site_id>/active/", views.SiteActiveView.as_view(), name="site_active"),
]
