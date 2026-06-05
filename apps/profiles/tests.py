from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.profiles.models import Profile
from apps.profiles.utils import detect_whatsapp_link_type
from apps.links.models import Link
from apps.leads.models import Lead

User = get_user_model()

class WhatsAppLinkDetectionTest(TestCase):
    def test_link_detection_types(self):
        test_cases = [
            ("https://wa.me/p/123456", "business"),
            ("https://wa.me/message/ABCDEF", "business"),
            ("https://wa.me/919999999999", "chat"),
            ("https://api.whatsapp.com/send?phone=919999999999", "chat"),
            ("https://chat.whatsapp.com/community/ABCDEF12345", "community"),
            ("https://chat.whatsapp.com/invite/123456789", "group"),
            ("https://chat.whatsapp.com/123456789", "group"),
            ("https://whatsapp.com/channel/XYZ123", "channel"),
            ("https://www.whatsapp.com/community/XYZ", "community"),
            ("https://example.com/other", "other"),
            ("https://www.whatsapp.com/intl/en/channel/XYZ123", "channel"),
            ("chat.whatsapp.com/invite/123456789", "group"),
            ("whatsapp.com/channel/XYZ123", "channel"),
        ]
        for url, expected in test_cases:
            with self.subTest(url=url):
                self.assertEqual(detect_whatsapp_link_type(url), expected)

class ProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+919999999999")

    def test_profile_creation_lowercase_handle(self):
        profile = Profile.objects.create(
            user=self.user,
            handle="John_Doe",
            display_name="John Doe"
        )
        self.assertEqual(profile.handle, "john_doe")

    def test_profile_reserved_handle_validation(self):
        profile = Profile(
            user=self.user,
            handle="admin",
            display_name="Admin"
        )
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_profile_invalid_handle_format(self):
        invalid_handles = ["ab", "a!b", "john.doe", "a" * 31]
        for handle in invalid_handles:
            profile = Profile(user=self.user, handle=handle, display_name="Test")
            with self.assertRaises(ValidationError):
                profile.full_clean()

class LinkAndLeadModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+919999999999")
        self.profile = Profile.objects.create(
            user=self.user,
            handle="test_user",
            display_name="Test User"
        )

    def test_link_auto_fields_on_save(self):
        link = Link.objects.create(
            profile=self.profile,
            url="https://chat.whatsapp.com/invite/group123",
            label="My Group"
        )
        self.assertEqual(link.surface_type, "group")
        self.assertEqual(link.cta_text, "Join our WhatsApp Group")

    def test_other_link_fails_validation(self):
        link = Link(
            profile=self.profile,
            url="https://example.com/somepage",
            label="Website"
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_link_limit_constraint(self):
        # Create 5 active links
        for i in range(5):
            Link.objects.create(
                profile=self.profile,
                url=f"https://wa.me/91999999999{i}",
                label=f"Link {i}",
                is_active=True
            )
        # Attempt to create a 6th active link should fail clean validation
        extra_link = Link(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Link 6",
            is_active=True
        )
        with self.assertRaises(ValidationError):
            extra_link.full_clean()

    def test_link_uniqueness_constraint(self):
        # Create initial link
        Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Original Link"
        )
        # Create duplicate link on same profile
        dup_link = Link(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Duplicate Link"
        )
        with self.assertRaises(ValidationError):
            dup_link.full_clean()

    def test_lead_snapshot_on_save(self):
        link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Chat Now",
            cta_text="Talk to Us"
        )
        lead = Lead.objects.create(
            link=link,
            name="Alice",
            email="alice@example.com",
            whatsapp_number="+918888888888",
            message="Hello!"
        )
        self.assertEqual(lead.link_url_snapshot, link.url)
        self.assertEqual(lead.link_label_snapshot, link.label)
        self.assertEqual(lead.cta_text_snapshot, link.cta_text)

        # Deleting the link should keep the snapshots intact
        link.delete()
        lead.refresh_from_db()
        self.assertIsNone(lead.link)
        self.assertEqual(lead.link_url_snapshot, "https://wa.me/919999999999")
        self.assertEqual(lead.link_label_snapshot, "Chat Now")
        self.assertEqual(lead.cta_text_snapshot, "Talk to Us")

from django.urls import reverse

class ViewsIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+919999999999")
        self.profile = Profile.objects.create(
            user=self.user,
            handle="testprofile",
            display_name="Test Profile",
            is_visible=True
        )
        self.link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Chat"
        )

    def test_public_profile_view_renders(self):
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Profile")
        self.assertContains(response, "Chat")

    def test_public_profile_anonymous_renders_modal_buttons(self):
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'hx-get="/testprofile/capture/{self.link.id}/"')
        self.assertContains(response, '<button')

    def test_public_profile_owner_renders_direct_links(self):
        self.client.force_login(self.user)
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'hx-get="/testprofile/capture/{self.link.id}/"')
        self.assertContains(response, f'href="{self.link.url}"')

    def test_public_profile_go_to_dashboard_flow(self):
        self.client.force_login(self.user)
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        
        dashboard_url = reverse("profiles:dashboard")
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)



    def test_private_profile_visibility_guard(self):
        self.profile.is_visible = False
        self.profile.save()
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        # Forbidden since it is private and we are not logged in as owner
        self.assertEqual(response.status_code, 403)

    def test_capture_lead_success_flow(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Bob",
            "email": "bob@example.com",
            "whatsapp_number": "+917777777777",
            "message": "Hello!",
            "phone": ""  # honeypot must be empty
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're all set!")
        self.assertTrue(Lead.objects.filter(name="Bob").exists())

    def test_capture_lead_get_renders_form_fields(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Before we connect you")
        self.assertContains(response, "Your Name")

    def test_capture_lead_honeypot_silently_ignored(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Bot",
            "email": "bot@example.com",
            "whatsapp_number": "+917777777777",
            "message": "Spam",
            "phone": "spam_phone_number"  # honeypot filled!
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        # Pretends success but does not create Lead in DB
        self.assertFalse(Lead.objects.filter(name="Bot").exists())

    def test_export_leads_csv(self):
        self.client.force_login(self.user)
        url = reverse("leads:export_leads")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_root_path_redirects_anonymous_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, reverse("authentication:login"))

    def test_root_path_redirects_authenticated_to_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("profiles:dashboard"))

    def test_login_fails_for_non_existent_user(self):
        url = reverse("authentication:login")
        payload = {"phone_number": "+918888888888"}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone number not registered", status_code=200)

    def test_signup_fails_for_existing_user(self):
        url = reverse("authentication:signup")
        payload = {"phone_number": "+919999999999"}  # self.user's phone
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone already registered", status_code=200)

    def test_signup_success_flow(self):
        url = reverse("authentication:signup_verify")
        payload = {
            "phone_number": "+917777777777",
            "otp": "123456"  # dev bypass code
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], "/dashboard/setup/")

    def test_login_success_flow(self):
        url = reverse("authentication:verify")
        payload = {
            "phone_number": "+919999999999",  # self.user's phone
            "otp": "123456"  # dev bypass code
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], "/dashboard/")

    def test_add_link_view_success(self):
        self.client.force_login(self.user)
        url = reverse("profiles:add_link")
        payload = {
            "label": "Support Link",
            "url": "https://wa.me/919999999998",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Support Link")
        self.assertContains(response, "https://wa.me/919999999998")

    def test_add_link_view_validation_error(self):
        self.client.force_login(self.user)
        url = reverse("profiles:add_link")
        payload = {
            "label": "Invalid Link",
            "url": "not-a-url",
            "surface_type": "other"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        # Should display validation message
        self.assertContains(response, "id=\"link-add-msg\"", status_code=200)

    def test_add_duplicate_link_view_error(self):
        self.client.force_login(self.user)
        # Create initial link
        Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999998",
            label="Support Link"
        )
        url = reverse("profiles:add_link")
        payload = {
            "label": "Duplicate Link",
            "url": "https://wa.me/919999999998",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This link is already put up by the user.")

    def test_toggle_link_view_limit_exceeded(self):
        self.profile.is_visible = False
        self.profile.save()
        for i in range(4):
            Link.objects.create(
                profile=self.profile,
                url=f"https://wa.me/91999999999{i}",
                label=f"Active Link {i}",
                is_active=True
            )
        inactive_link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999988",
            label="Inactive Link",
            is_active=False
        )
        self.client.force_login(self.user)
        url = reverse("profiles:toggle_link", kwargs={"pk": inactive_link.pk})
        response = self.client.post(url, {"is_active": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cannot activate. Limit is 5 active links.")

    def test_soft_cap_warning_on_4th_link(self):
        self.client.force_login(self.user)
        # Create 2 active links (plus 1 from setUp = 3 active links)
        for i in range(2):
            Link.objects.create(
                profile=self.profile,
                url=f"https://wa.me/91999999999{i}",
                label=f"Link {i}",
                is_active=True
            )
        url = reverse("profiles:add_link")
        payload = {
            "label": "4th Link",
            "url": "https://wa.me/919999999998",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soft cap warning: you have 4 active links. Limit is 5.")

    def test_login_auto_prepending_10_digits(self):
        url = reverse("authentication:verify")
        payload = {
            "phone_number": "9999999999",  # 10 digits matches self.user (+919999999999)
            "otp": "123456"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], "/dashboard/")

    def test_logout_rejects_get(self):
        self.client.force_login(self.user)
        url = reverse("authentication:logout")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_logout_accepts_post_and_redirects(self):
        self.client.force_login(self.user)
        url = reverse("authentication:logout")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("authentication:login"))

    def test_link_analytics_view(self):
        self.client.force_login(self.user)
        # Create a lead for self.link to populate stats
        Lead.objects.create(
            link=self.link,
            name="Test Lead",
            email="lead@test.com",
            whatsapp_number="+919876543210",
            message="Interested",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        url = reverse("profiles:link_analytics", kwargs={"pk": self.link.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mobile")
        self.assertContains(response, "Safari")
        self.assertContains(response, "1 lead")

    def test_links_list_view_authenticated(self):
        self.client.force_login(self.user)
        url = reverse("profiles:links_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chat")

    def test_links_list_view_anonymous(self):
        url = reverse("profiles:links_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_edit_link_view_get_authenticated(self):
        self.link.surface_type = "group"
        self.link.save()
        self.client.force_login(self.user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Chat"')
        self.assertContains(response, 'value="https://wa.me/919999999999"')
        self.assertContains(response, 'selected')  # Group option is selected

    def test_edit_link_view_post_success(self):
        self.client.force_login(self.user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        payload = {
            "label": "Updated Label",
            "url": "https://wa.me/918888888888",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertIn("closeEditModal", response["HX-Trigger"])
        self.assertIn("linkListChanged", response["HX-Trigger"])
        
        self.link.refresh_from_db()
        self.assertEqual(self.link.label, "Updated Label")
        self.assertEqual(self.link.url, "https://wa.me/918888888888")
        self.assertEqual(self.link.surface_type, "group")

    def test_edit_link_view_post_validation_error(self):
        self.client.force_login(self.user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        payload = {
            "label": "Updated Label",
            "url": "https://example.com/invalid",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only WhatsApp links are allowed on XPAND.")
        
        self.link.refresh_from_db()
        self.assertNotEqual(self.link.label, "Updated Label")

    def test_edit_link_view_forbidden(self):
        other_user = User.objects.create_user(phone_number="+918888888888")
        self.client.force_login(other_user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        
        # Should return 404 since it's not the owner's link
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        response = self.client.post(url, {
            "label": "Hack Attempt",
            "url": "https://wa.me/918888888888",
            "surface_type": "group"
        })
        self.assertEqual(response.status_code, 404)



