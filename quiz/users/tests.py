from django.contrib.auth import get_user_model
from django.test import TestCase


class RegisterViewTests(TestCase):
    def test_register_get_renders_page(self):
        resp = self.client.get("/auth/register/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "registration/register.html")

    def test_register_post_valid_creates_user_and_redirects(self):
        User = get_user_model()
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "password1": "StrongPass12345!",
            "password2": "StrongPass12345!",
        }

        resp = self.client.post("/auth/register/", data=payload)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/")

        self.assertTrue(User.objects.filter(username="testuser").exists())

        # Пользователь должен быть залогинен после регистрации
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_register_post_invalid_does_not_create_user(self):
        User = get_user_model()
        payload = {
            "username": "baduser",
            "email": "bad@example.com",
            "password1": "StrongPass12345!",
            "password2": "DifferentPass12345!",
        }

        resp = self.client.post("/auth/register/", data=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "registration/register.html")
        self.assertFalse(User.objects.filter(username="baduser").exists())