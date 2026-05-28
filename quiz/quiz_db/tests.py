from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AnswerOption, Question, QuestionType, Quiz, QuizAttempt


class QuizDbViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="TeacherPass12345!",
        )
        self.student = User.objects.create_user(
            username="student",
            email="student@example.com",
            password="StudentPass12345!",
        )

        self.quiz = Quiz.objects.create(
            title="Тест 1",
            description="Описание",
            time_limit_minutes=10,
            is_published=True,
            max_attempts=2,
            author=self.teacher,
        )
        self.question = Question.objects.create(
            quiz=self.quiz,
            text="Вопрос 1?",
            question_type=QuestionType.SINGLE,
            order=1,
        )
        self.opt1 = AnswerOption.objects.create(
            question=self.question, text="Ответ A", is_correct=True, order=1
        )
        self.opt2 = AnswerOption.objects.create(
            question=self.question, text="Ответ B", is_correct=False, order=2
        )

    def test_home_page_ok(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "index.html")

    def test_quiz_list_page_ok(self):
        resp = self.client.get(reverse("quiz_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "quiz_list.html")

    def test_quiz_detail_anonymous_ok(self):
        resp = self.client.get(reverse("quiz_detail", args=[self.quiz.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "quiz_db/quiz_detail.html")

    def test_profile_requires_login(self):
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 302)

    def test_quiz_play_requires_login(self):
        resp = self.client.get(reverse("quiz_detail", args=[self.quiz.id]) + "?q=1")
        self.assertEqual(resp.status_code, 302)

    def test_quiz_play_logged_in_renders_question(self):
        self.client.login(username="student", password="StudentPass12345!")
        resp = self.client.get(reverse("quiz_detail", args=[self.quiz.id]) + "?q=1")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "quiz_detail.html")

        self.assertTrue(
            QuizAttempt.objects.filter(student=self.student, quiz=self.quiz).exists()
        )

    def test_toggle_favorite_requires_post_and_login(self):
        # аноним — редирект на login
        resp = self.client.post(
            reverse("toggle_favorite", args=[self.quiz.id]), HTTP_REFERER="/tests/"
        )
        self.assertEqual(resp.status_code, 302)

        self.client.login(username="student", password="StudentPass12345!")

        # GET не разрешён
        resp = self.client.get(reverse("toggle_favorite", args=[self.quiz.id]))
        self.assertEqual(resp.status_code, 405)

        # POST — ок
        resp = self.client.post(
            reverse("toggle_favorite", args=[self.quiz.id]), HTTP_REFERER="/tests/"
        )
        self.assertEqual(resp.status_code, 302)

    def test_submit_answer_flow_finishes_and_shows_result(self):
        self.client.login(username="student", password="StudentPass12345!")

        # создаём активную попытку через play
        self.client.get(reverse("quiz_detail", args=[self.quiz.id]) + "?q=1")

        resp = self.client.post(
            reverse("submit_answer", args=[self.quiz.id]),
            data={
                "q": "1",
                f"answer_{self.question.id}": str(self.opt1.id),
            },
        )
        self.assertEqual(resp.status_code, 302)

        # после 1 вопроса редирект на результат
        self.assertEqual(resp["Location"], reverse("quiz_result", args=[self.quiz.id]))

        resp = self.client.get(reverse("quiz_result", args=[self.quiz.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "result.html")