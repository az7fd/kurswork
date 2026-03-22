# movies/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from .models import Users, Movies, Ratings, Genres, MovieGenres, Recommendations
from .recommendation_engine import RecommendationEngine
import json

# Создаем экземпляр движка рекомендаций
recommendation_engine = RecommendationEngine()


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.POST.get('email')
        birth_date = request.POST.get('birth_date')

        # Валидация
        errors = []

        if not username or not password or not email:
            errors.append("Все поля обязательны для заполнения")

        if password != confirm_password:
            errors.append("Пароли не совпадают")

        if len(password) > 16:
            errors.append("Пароль не должен превышать 16 символов")

        if Users.objects.filter(username=username).exists():
            errors.append("Пользователь с таким именем уже существует")

        if Users.objects.filter(email=email).exists():
            errors.append("Пользователь с таким email уже существует")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'register.html')

        # Создание пользователя
        user = Users(
            username=username,
            password=password,
            email=email,
            birth_date=birth_date if birth_date else None
        )
        user.save()

        messages.success(request, "Регистрация прошла успешно! Теперь вы можете войти.")
        return redirect('auth')

    return render(request, 'register.html')


def auth_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, "Заполните все поля")
            return render(request, 'auth.html')

        try:
            user = Users.objects.get(username=username)
        except Users.DoesNotExist:
            try:
                user = Users.objects.get(email=username)
            except:
                messages.error(request, "Неверно введенное имя пользователя или email")
                return render(request, 'auth.html')

        if user.password == password:
            request.session['user_id'] = user.id
            request.session['username'] = user.username

            # Генерируем первые рекомендации при входе
            recommendation_engine.generate_for_user(user.id, force=True)

            messages.success(request, f"Добро пожаловать, {user.username}!")
            return redirect('films')
        else:
            messages.error(request, "Неверный логин или пароль")
            return render(request, 'auth.html')

    return render(request, 'auth.html')


def logout_view(request):
    request.session.flush()
    messages.success(request, "Вы успешно вышли из системы")
    return redirect('auth')


def films_view(request):
    """Главная страница с фильмами и рекомендациями"""
    # Проверяем, авторизован ли пользователь
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "Необходимо войти в систему")
        return redirect('auth')

    try:
        user = Users.objects.get(id=user_id)
    except Users.DoesNotExist:
        request.session.flush()
        return redirect('auth')

    # Получаем рекомендации пользователя
    recommendations = Recommendations.objects.filter(
        user=user
    ).select_related('movie').order_by('-predicted_rating')[:12]

    # Если нет рекомендаций, генерируем
    if not recommendations.exists():
        recommendation_engine.generate_for_user(user.id, force=True)
        recommendations = Recommendations.objects.filter(
            user=user
        ).select_related('movie').order_by('-predicted_rating')[:12]

    # Получаем популярные фильмы
    popular_movies = Movies.objects.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__rating')
    ).filter(rating_count__gt=0).order_by('-rating_count', '-avg_rating')[:6]

    # Получаем недавно оцененные пользователем фильмы
    recently_rated = Ratings.objects.filter(
        user=user
    ).select_related('movie').order_by('-rated_at')[:6]

    # Получаем все жанры для фильтра
    all_genres = Genres.objects.all()

    context = {
        'user': user,
        'recommendations': recommendations,
        'popular_movies': popular_movies,
        'recently_rated': recently_rated,
        'all_genres': all_genres,
        'user_ratings_count': Ratings.objects.filter(user=user).count(),
    }

    return render(request, 'films.html', context)


def movie_detail_view(request, movie_id):
    """Страница детальной информации о фильме"""
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "Необходимо войти в систему")
        return redirect('auth')

    movie = get_object_or_404(Movies, id=movie_id)

    # Получаем жанры фильма
    genres = MovieGenres.objects.filter(movie=movie).select_related('genre')

    # Получаем все оценки фильма
    ratings = Ratings.objects.filter(movie=movie).select_related('user')

    # Статистика оценок
    rating_stats = {
        'count': ratings.count(),
        'avg': ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
        'distribution': {}
    }

    # Распределение оценок
    for i in range(1, 11):
        rating_stats['distribution'][i] = ratings.filter(rating=i).count()

    # Проверяем, оценил ли текущий пользователь этот фильм
    user_rating = None
    try:
        user_rating = Ratings.objects.get(
            user_id=user_id,
            movie=movie
        )
    except Ratings.DoesNotExist:
        pass

    # Получаем похожие фильмы (по жанрам)
    similar_movies = get_similar_movies(movie, limit=6)

    context = {
        'movie': movie,
        'genres': genres,
        'ratings': ratings.order_by('-rated_at')[:10],  # Последние 10 оценок
        'rating_stats': rating_stats,
        'user_rating': user_rating,
        'similar_movies': similar_movies,
    }

    return render(request, 'movie_detail.html', context)


def get_similar_movies(movie, limit=6):
    """Находит похожие фильмы по жанрам"""
    # Получаем жанры текущего фильма
    movie_genres = MovieGenres.objects.filter(
        movie=movie
    ).values_list('genre_id', flat=True)

    if not movie_genres:
        return Movies.objects.order_by('?')[:limit]

    # Находим фильмы с такими же жанрами
    similar = Movies.objects.filter(
        moviegenres__genre_id__in=movie_genres
    ).exclude(
        id=movie.id
    ).annotate(
        common_genres=Count('moviegenres')
    ).order_by('-common_genres', '?')[:limit]

    return similar


def rate_movie_view(request, movie_id):
    """Ajax-обработка оценки фильма"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Не авторизован'}, status=401)

    rating_value = request.POST.get('rating')

    if not rating_value:
        return JsonResponse({'error': 'Нет оценки'}, status=400)

    try:
        rating_value = int(rating_value)
        if rating_value < 1 or rating_value > 10:
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'Оценка должна быть от 1 до 10'}, status=400)

    # Сохраняем или обновляем оценку
    rating, created = Ratings.objects.update_or_create(
        user_id=user_id,
        movie_id=movie_id,
        defaults={'rating': rating_value}
    )

    # Перегенерируем рекомендации
    recommendation_engine.generate_for_user(user_id, force=True)

    return JsonResponse({
        'success': True,
        'rating': rating_value,
        'created': created
    })


def catalog_view(request):
    """Каталог всех фильмов с фильтрацией"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('auth')

    # Базовый запрос
    movies = Movies.objects.all()

    # Фильтры
    genre_id = request.GET.get('genre')
    year_from = request.GET.get('year_from')
    year_to = request.GET.get('year_to')
    min_rating = request.GET.get('min_rating')
    search = request.GET.get('search')

    if genre_id and genre_id.isdigit():
        movies = movies.filter(moviegenres__genre_id=genre_id)

    if year_from and year_from.isdigit():
        movies = movies.filter(year__gte=year_from)

    if year_to and year_to.isdigit():
        movies = movies.filter(year__lte=year_to)

    if min_rating and min_rating.replace('.', '').isdigit():
        movies = movies.filter(imbd_rating__gte=float(min_rating))

    if search:
        movies = movies.filter(title__icontains=search)

    # Агрегируем средние оценки пользователей
    movies = movies.annotate(
        user_rating_avg=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).distinct()

    # Сортировка
    sort = request.GET.get('sort', '-year')
    movies = movies.order_by(sort)

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(movies, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Все жанры для фильтра
    all_genres = Genres.objects.annotate(
        movie_count=Count('moviegenres')
    ).filter(movie_count__gt=0)

    context = {
        'page_obj': page_obj,
        'all_genres': all_genres,
        'current_filters': {
            'genre': genre_id,
            'year_from': year_from,
            'year_to': year_to,
            'min_rating': min_rating,
            'search': search,
            'sort': sort,
        }
    }

    return render(request, 'catalog.html', context)


def my_ratings_view(request):
    """Страница с оценками пользователя"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('auth')

    ratings = Ratings.objects.filter(
        user_id=user_id
    ).select_related('movie').order_by('-rated_at')

    # Подсчет распределения оценок (вставляем сюда)
    from collections import Counter

    # Получаем список всех оценок пользователя
    rating_values = list(ratings.values_list('rating', flat=True))

    # Подсчитываем количество каждой оценки
    rating_counts = dict(Counter(rating_values))

    # Добавляем все оценки от 1 до 10, даже если их нет
    for i in range(1, 11):
        if i not in rating_counts:
            rating_counts[i] = 0

    # Для удобства в шаблоне можно создать список с процентами
    total = ratings.count()
    rating_distribution = []
    if total > 0:
        for i in range(1, 11):
            count = rating_counts.get(i, 0)
            percentage = (count / total * 100) if total > 0 else 0
            rating_distribution.append({
                'value': i,
                'count': count,
                'percentage': round(percentage, 1)
            })

    context = {
        'ratings': ratings,
        'total_count': ratings.count(),
        'avg_rating': ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
        'rating_counts': rating_counts,
        'rating_distribution': rating_distribution,  # Добавляем для удобства
    }

    return render(request, 'my_ratings.html', context)


def refresh_recommendations_view(request):
    """Принудительное обновление рекомендаций"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('auth')

    recommendation_engine.generate_for_user(user_id, force=True)
    messages.success(request, 'Рекомендации обновлены!')
    return redirect('films')

from .forms import MovieForm

def add_films(request):
    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('catalog')
    else:
        form = MovieForm()
    return render(request, 'add_films.html', {'form': form})


def edit_film(request, movie_id):
    """Редактирование фильма"""
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "Необходимо войти в систему")
        return redirect('auth')

    movie = get_object_or_404(Movies, id=movie_id)

    # Получаем пользователя из сессии
    try:
        current_user = Users.objects.get(id=user_id)
    except Users.DoesNotExist:
        request.session.flush()
        messages.error(request, "Пользователь не найден")
        return redirect('auth')

    # Любой авторизованный пользователь может редактировать
    # (убрали проверку прав)

    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES, instance=movie)

        # Проверка на удаление постера
        if request.POST.get('clear_poster') and movie.poster:
            movie.poster.delete()
            movie.poster = None

        if form.is_valid():
            form.save()
            messages.success(request, f'Фильм "{movie.title}" успешно обновлен!')
            return redirect('movie_detail', movie_id=movie.id)
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    else:
        form = MovieForm(instance=movie)

    context = {
        'form': form,
        'movie': movie,
        'user': current_user,
    }
    return render(request, 'edit_film.html', context)


def delete_film(request, movie_id):
    """Удаление фильма"""
    movie = get_object_or_404(Movies, id=movie_id)

    # Проверка прав (только автор или админ)
    if not (request.user.is_staff or movie.added_by == request.user):
        messages.error(request, 'У вас нет прав для удаления этого фильма')
        return redirect('movie_detail', movie_id=movie.id)

    if request.method == 'POST':
        title = movie.title
        movie.delete()
        messages.success(request, f'Фильм "{title}" успешно удален')
        return redirect('catalog')

    # GET запрос - показываем страницу подтверждения
    context = {
        'movie': movie,
        'user': request.user,
    }
    return render(request, 'confirm_delete.html', context)