
from django.contrib import admin
from django.urls import path
from films_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.auth_view, name="auth"),
    path('register/', views.register_view, name="register"),
    path('logout/', views.logout_view, name="logout"),
    path('films/', views.films_view, name="films"),
    path('movie/<int:movie_id>/', views.movie_detail_view, name="movie_detail"),
    path('movie/<int:movie_id>/rate/', views.rate_movie_view, name="rate_movie"),
    path('catalog/', views.catalog_view, name="catalog"),
    path('my-ratings/', views.my_ratings_view, name="my_ratings"),
    path('refresh-recommendations/', views.refresh_recommendations_view, name="refresh_recommendations"),
    path('add-films', views.add_films, name="add_films"),
    path('movie/<int:movie_id>/edit/', views.edit_film, name='edit_film'),
    path('movie/<int:movie_id>/delete/', views.delete_film, name='delete_film'),
]