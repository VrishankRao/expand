from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.profiles.models import Profile

User = get_user_model()

class AdminPanelViewsTest(TestCase):
    def setUp(self):
        # Create standard user
        self.standard_user = User.objects.create_user(phone_number="+911111111111", password="password123")
        self.standard_profile = Profile.objects.create(
            user=self.standard_user,
            handle="standard_user",
            display_name="Standard User",
            is_premium=False
        )

        # Create premium user
        self.premium_user = User.objects.create_user(phone_number="+912222222222", password="password123")
        self.premium_profile = Profile.objects.create(
            user=self.premium_user,
            handle="premium_user",
            display_name="Premium User",
            is_premium=True
        )

        # Create staff user
        self.staff_user = User.objects.create_superuser(phone_number="+919999999999", password="password123")

    def test_anonymous_redirect_to_login(self):
        urls = [
            reverse("admin_panel:dashboard"),
            reverse("admin_panel:user_detail", kwargs={"handle": "standard_user"}),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("admin_panel:login"), response.url)

    def test_non_staff_redirect_to_login(self):
        self.client.login(phone_number="+911111111111", password="password123")
        urls = [
            reverse("admin_panel:dashboard"),
            reverse("admin_panel:user_detail", kwargs={"handle": "standard_user"}),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("admin_panel:login"), response.url)

    def test_staff_access_success(self):
        self.client.login(phone_number="+919999999999", password="password123")
        
        # Test dashboard
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Standard User")
        self.assertContains(response, "Premium User")
        self.assertContains(response, "3") # Total users (standard + premium + staff)
        
        # Test user detail
        response = self.client.get(reverse("admin_panel:user_detail", kwargs={"handle": "standard_user"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Standard User")
        self.assertNotContains(response, "Delete") # Read-only view
        self.assertNotContains(response, "Edit")

    def test_toggle_visibility_action(self):
        self.client.login(phone_number="+919999999999", password="password123")
        self.assertFalse(self.standard_profile.is_visible)
        
        # Toggle visibility to True
        response = self.client.post(
            reverse("admin_panel:toggle_visibility", kwargs={"handle": "standard_user"}),
            {"is_visible": "true"}
        )
        self.assertEqual(response.status_code, 200)
        self.standard_profile.refresh_from_db()
        self.assertTrue(self.standard_profile.is_visible)

        # Toggle visibility back to False
        response = self.client.post(
            reverse("admin_panel:toggle_visibility", kwargs={"handle": "standard_user"}),
            {"is_visible": "false"}
        )
        self.assertEqual(response.status_code, 200)
        self.standard_profile.refresh_from_db()
        self.assertFalse(self.standard_profile.is_visible)
