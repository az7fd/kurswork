# movies/recommendation_engine.py
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Users, Movies, Ratings, Recommendations, MovieGenres
import logging

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Движок рекомендаций на основе коллаборативной фильтрации
    """

    def __init__(self):
        pass

    def get_algorithm_name(self, user_id):
        """Выбирает алгоритм в зависимости от количества оценок пользователя"""
        try:
            user = Users.objects.get(id=user_id)
            ratings_count = Ratings.objects.filter(user=user).count()

            if ratings_count < 3:
                return 'popular'  # Мало оценок - показываем популярное
            elif ratings_count < 10:
                return 'content_based'  # Средне оценок - по жанрам
            else:
                return 'hybrid'  # Много оценок - гибридный
        except Users.DoesNotExist:
            return 'popular'

    def get_user_based_recommendations(self, user_id, n=12):
        """
        User-based collaborative filtering
        Находит похожих пользователей и рекомендует их фильмы
        """
        try:
            user = Users.objects.get(id=user_id)
        except Users.DoesNotExist:
            return []

        # Получаем оценки текущего пользователя
        user_ratings = Ratings.objects.filter(user=user)
        user_rated_movies = set(user_ratings.values_list('movie_id', flat=True))

        # Если пользователь ничего не оценил - возвращаем популярные фильмы
        if not user_ratings.exists():
            return self._get_popular_movies(n)

        # Находим других пользователей, которые оценили те же фильмы
        similar_users = self._find_similar_users(user, user_rated_movies)

        if not similar_users:
            return self._get_popular_movies(n)

        # Собираем фильмы похожих пользователей
        candidate_movies = {}

        for similar_user, similarity_score in similar_users[:10]:
            # Получаем оценки похожего пользователя
            similar_ratings = Ratings.objects.filter(
                user=similar_user
            ).exclude(
                movie_id__in=user_rated_movies
            ).select_related('movie')[:30]

            for rating in similar_ratings:
                if rating.movie_id not in candidate_movies:
                    candidate_movies[rating.movie_id] = {
                        'movie': rating.movie,
                        'score': 0,
                        'count': 0
                    }

                # Взвешиваем по сходству пользователей и оценке
                candidate_movies[rating.movie_id]['score'] += rating.rating * similarity_score
                candidate_movies[rating.movie_id]['count'] += 1

        # Вычисляем средневзвешенный score
        recommendations = []
        for movie_id, data in candidate_movies.items():
            if data['count'] > 0:
                avg_score = data['score'] / data['count']
                recommendations.append((data['movie'], avg_score))

        # Сортируем по убыванию
        recommendations.sort(key=lambda x: x[1], reverse=True)

        return [movie for movie, _ in recommendations[:n]]

    def _find_similar_users(self, user, user_movies, limit=20):
        """
        Находит похожих пользователей на основе общих оценок
        """
        similar_users = []

        # Получаем всех пользователей, кроме текущего
        other_users = Users.objects.exclude(id=user.id)

        for other_user in other_users:
            # Получаем общие фильмы
            common_movies = Ratings.objects.filter(
                user=other_user,
                movie_id__in=user_movies
            ).count()

            if common_movies >= 2:  # Хотя бы 2 общих фильма
                # Простая метрика сходства - процент общих фильмов
                similarity = common_movies / max(len(user_movies), 5)
                similar_users.append((other_user, similarity))

        # Сортируем по убыванию сходства
        similar_users.sort(key=lambda x: x[1], reverse=True)

        return similar_users[:limit]

    def get_content_based_recommendations(self, user_id, n=12):
        """
        Content-based рекомендации на основе любимых жанров
        """
        try:
            user = Users.objects.get(id=user_id)
        except Users.DoesNotExist:
            return self._get_popular_movies(n)

        # Находим любимые жанры пользователя (по высоким оценкам)
        favorite_genres = set()
        high_ratings = Ratings.objects.filter(
            user=user,
            rating__gte=7  # Оценки 7 и выше считаем любимыми
        ).select_related('movie')

        for rating in high_ratings:
            movie_genres = MovieGenres.objects.filter(
                movie=rating.movie
            ).select_related('genre')
            for mg in movie_genres:
                favorite_genres.add(mg.genre)

        if not favorite_genres:
            return self._get_popular_movies(n)

        # Получаем фильмы, которые пользователь уже смотрел
        watched_movies = set(Ratings.objects.filter(
            user=user
        ).values_list('movie_id', flat=True))

        # Ищем фильмы с любимыми жанрами
        candidates = Movies.objects.filter(
            moviegenres__genre__in=favorite_genres
        ).exclude(
            id__in=watched_movies
        ).distinct().annotate(
            avg_rating=Avg('ratings__rating')
        ).order_by('-avg_rating')[:n]

        return list(candidates)

    def get_hybrid_recommendations(self, user_id, n=12):
        """
        Гибридные рекомендации - комбинация разных методов
        """
        # Получаем рекомендации разными методами
        user_based = self.get_user_based_recommendations(user_id, n=8)
        content_based = self.get_content_based_recommendations(user_id, n=8)

        # Комбинируем, убирая дубликаты
        all_movies = []
        seen_ids = set()

        # Сначала user-based (они обычно точнее)
        for movie in user_based:
            if movie.id not in seen_ids:
                all_movies.append(movie)
                seen_ids.add(movie.id)

        # Потом content-based
        for movie in content_based:
            if movie.id not in seen_ids and len(all_movies) < n:
                all_movies.append(movie)
                seen_ids.add(movie.id)

        # Если все еще мало, добавляем популярные
        if len(all_movies) < n:
            popular = self._get_popular_movies(n * 2)
            for movie in popular:
                if movie.id not in seen_ids and len(all_movies) < n:
                    all_movies.append(movie)
                    seen_ids.add(movie.id)

        return all_movies[:n]

    def _get_popular_movies(self, n=12):
        """
        Возвращает популярные фильмы (много оценок + высокий рейтинг)
        """
        popular = Movies.objects.annotate(
            rating_count=Count('ratings'),
            avg_rating=Avg('ratings__rating')
        ).filter(
            rating_count__gt=0
        ).order_by('-rating_count', '-avg_rating')[:n]

        return list(popular)

    def generate_for_user(self, user_id, force=False):
        """
        Генерирует и сохраняет рекомендации для пользователя
        """
        # Проверяем, есть ли уже свежие рекомендации
        if not force:
            recent = Recommendations.objects.filter(
                user_id=user_id,
                generated_at__gte=timezone.now() - timedelta(hours=24)
            ).exists()

            if recent:
                logger.info(f"User {user_id} already has fresh recommendations")
                return

        # Выбираем алгоритм
        algorithm = self.get_algorithm_name(user_id)

        # Получаем рекомендации соответствующим методом
        if algorithm == 'popular':
            recommended_movies = self._get_popular_movies(20)
        elif algorithm == 'content_based':
            recommended_movies = self.get_content_based_recommendations(user_id, 20)
        elif algorithm == 'hybrid':
            recommended_movies = self.get_hybrid_recommendations(user_id, 20)
        else:
            recommended_movies = self.get_user_based_recommendations(user_id, 20)

        # Удаляем старые рекомендации
        Recommendations.objects.filter(user_id=user_id).delete()

        # Сохраняем новые
        for movie in recommended_movies:
            # Вычисляем прогнозируемую оценку
            predicted = self._predict_rating(user_id, movie.id)

            Recommendations.objects.create(
                user_id=user_id,
                movie=movie,
                predicted_rating=predicted,
                algorithm=algorithm
            )

        logger.info(f"Generated {len(recommended_movies)} recommendations for user {user_id} using {algorithm}")

    def _predict_rating(self, user_id, movie_id):
        """
        Предсказывает оценку пользователя для фильма
        """
        # Средняя оценка пользователя
        user_avg = Ratings.objects.filter(
            user_id=user_id
        ).aggregate(avg=Avg('rating'))['avg']

        if not user_avg:
            user_avg = 7.0  # значение по умолчанию

        # Средняя оценка фильма
        movie_avg = Ratings.objects.filter(
            movie_id=movie_id
        ).aggregate(avg=Avg('rating'))['avg']

        if not movie_avg:
            movie_avg = 7.0

        # Комбинируем
        return (user_avg * 0.6 + movie_avg * 0.4)