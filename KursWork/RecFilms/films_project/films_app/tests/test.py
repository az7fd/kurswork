from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from datetime import date, timedelta
import tempfile
import os

from .models import Users, Movies, Ratings, Genres, MovieGenres, Recommendations

class UsersModelTest(TestCase):
    """Тестирование модели пользователя"""

    def setUp(self):
        """Подготовка данных перед каждым тестом"""
        self.user_data = {
            'username': 'testuser',
            'password': 'testpass123',
            'email': 'test@example.com',
            'birth_date': date(1995, 5, 15)
        }
        self.user = Users.objects.create(**self.user_data)


def test_create_user_success(self):
    """Тест успешного создания пользователя"""
    user = Users.objects.get(username='testuser')
    self.assertEqual(user.username, 'testuser')
    self.assertEqual(user.email, 'test@example.com')
    self.assertEqual(user.birth_date, date(1995, 5, 15))
    self.assertIsNotNone(user.created_at)


class MoviesModelTest(TestCase):
    """Тестирование модели фильмов"""

    def setUp(self):
        """Подготовка данных перед каждым тестом"""
        self.test_poster = create_test_image()

        self.movie_data = {
            'title': 'Тестовый фильм',
            'year': 2023,
            'description': 'Описание тестового фильма',
            'imbd_rating': 8.5,
            'poster': self.test_poster
        }
        self.movie = Movies.objects.create(**self.movie_data)


class RatingsModelTest(TestCase):
    """Тестирование модели оценок"""

    def setUp(self):
        self.user = Users.objects.create(
            username='ratinguser',
            password='pass123',
            email='rating@example.com'
        )
        self.movie = Movies.objects.create(
            title='Оцениваемый фильм',
            year=2023,
            imbd_rating=7.0
        )

    def test_create_rating_success(self):
        """Тест успешного создания оценки"""
        rating = Ratings.objects.create(
            user=self.user,
            movie=self.movie,
            rating=9
        )
        self.assertEqual(rating.rating, 9)
        self.assertEqual(rating.user, self.user)
        self.assertEqual(rating.movie, self.movie)
