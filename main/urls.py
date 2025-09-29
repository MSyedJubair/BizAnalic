from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path('about', views.about, name='about'),
    path('features', views.features, name='features'),
    path("dashboard", views.dashboard, name="dashboard"),
    path("uploadfile", views.uploadfile, name="uploadfile"),
] 
