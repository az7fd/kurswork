from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

# Create your models here.
class Users(models.Model):
    username = models.CharField(max_length=40, unique=True)
    password = models.CharField(max_length=16)
    email = models.EmailField(unique=True)
    birth_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

class Movies(models.Model):
    title = models.CharField(max_length=100)
    year = models.IntegerField(validators=[MinValueValidator(1880)])
    description = models.TextField(blank=True)
    imbd_rating = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    poster = models.ImageField(upload_to='posters/')

    def __str__(self):
        return f"{self.title} ({self.year})"

    def average_rating(self):
        """Вычисляет средний рейтинг фильма"""
        ratings = self.ratings_set.all()
        if ratings:
            return sum(r.rating for r in ratings) / len(ratings)
        return None

class Ratings(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movies, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    rated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'movie')  # Чтобы пользователь не мог оценить фильм дважды

    def __str__(self):
        return f"{self.user.username} оценил {self.movie.title} на {self.rating}"

class Genres(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class MovieGenres(models.Model):
    movie = models.ForeignKey(Movies, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genres, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('movie', 'genre')  # Чтобы не было дубликатов

    def __str__(self):
        return f"{self.movie.title} - {self.genre.name}"

class Recommendations(models.Model):
    ALGORITHM_CHOICES = [
        ('user_based', 'На основе похожих пользователей'),
        ('item_based', 'На основе похожих фильмов'),
        ('content_based', 'На основе жанров'),
        ('hybrid', 'Гибридный алгоритм'),
        ('popular', 'Популярные фильмы'),
    ]

    movie = models.ForeignKey(Movies, on_delete=models.CASCADE)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    predicted_rating = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(10)])
    generated_at = models.DateTimeField(auto_now_add=True)
    algorithm = models.CharField(max_length=100)

    class Meta:
        unique_together = ('user', 'movie')  # Чтобы не было дубликатов рекомендаций

    def __str__(self):
        return f"Рекомендация {self.movie.title} для {self.user.username}"