# traversal/urls.py
from django.urls import path
from . import views

app_name = 'traversal'

urlpatterns = [
    path('', views.guide, name='guide'),
    path('graph/', views.graph, name='graph'),
    path('algorithm/', views.algorithm_page, name='algorithm_page'),
    path('app/', views.index, name='index'),
    path('api/stations/', views.get_stations, name='stations'),
    path('api/network/', views.get_network, name='network'),
    path('api/network/highlight/', views.get_network_highlight, name='network_highlight'),
    path('api/calculate/', views.calculate_path, name='calculate'),
    path('api/compare/', views.compare_algorithms, name='compare_algorithms'),
    path('api/report/<str:filename>/', views.download_report, name='download_report'),
    path('api/file/<str:filename>/', views.view_output_file, name='view_output_file'),
]