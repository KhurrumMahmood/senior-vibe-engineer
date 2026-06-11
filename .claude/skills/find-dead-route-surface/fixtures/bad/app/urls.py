from django.urls import path

from app.pages.sites import views

urlpatterns = [
    path("sites-prototype/", views.SitePrototypeView.as_view(), name="sites_prototype"),
]
