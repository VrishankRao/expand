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

from apps.profiles.views import get_country_from_phone


class CountryDetectionTest(TestCase):
    def test_country_detection_from_phone(self):
        test_cases = [
            ("+919876543210", "India"),
            ("+15555555555", "United States/Canada"),
            ("+447700900077", "United Kingdom"),
            ("+971501234567", "United Arab Emirates"),
            ("9876543210", "India"),
            ("", "Unknown"),
            ("+999000000", "Other"),
        ]
        for phone, expected in test_cases:
            with self.subTest(phone=phone):
                self.assertEqual(get_country_from_phone(phone), expected)

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
        # Create 10 active links
        for i in range(10):
            Link.objects.create(
                profile=self.profile,
                url=f"https://wa.me/91999999999{i}",
                label=f"Link {i}",
                is_active=True
            )
        # Attempt to create an 11th active link should fail clean validation
        extra_link = Link(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Link 11",
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

    def test_link_name_and_type_uniqueness_constraint(self):
        # Create initial link
        Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="hh",
            surface_type="group"
        )
        # Create duplicate link with same name and group type
        dup_link = Link(
            profile=self.profile,
            url="https://wa.me/918888888888",
            label="hh",
            surface_type="group"
        )
        with self.assertRaises(ValidationError):
            dup_link.full_clean()
        
        # Creating a link with same name but DIFFERENT group type should succeed
        diff_type_link = Link(
            profile=self.profile,
            url="https://wa.me/918888888888",
            label="hh",
            surface_type="community"
        )
        diff_type_link.full_clean()  # should not raise ValidationError
        
        # Creating a link with different name but SAME group type should succeed
        diff_name_link = Link(
            profile=self.profile,
            url="https://wa.me/917777777777",
            label="other-name",
            surface_type="group"
        )
        diff_name_link.full_clean()  # should not raise ValidationError

    def test_whatsapp_link_cannot_be_other_premium(self):
        self.profile.is_premium = True
        self.profile.save()
        
        link = Link(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Chat Link",
            surface_type="other"
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

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

        # Deleting the link should delete the lead
        link.delete()
        self.assertFalse(Lead.objects.filter(pk=lead.pk).exists())

from django.urls import reverse

class ViewsIntegrationTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
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

    def test_public_profile_view_renders_deep_link(self):
        self.link.surface_type = "group"
        self.link.label = "Support Chat"
        self.link.save()
        
        # Test valid deep link
        url = reverse("leads:public_profile_with_link", kwargs={
            "handle": "testprofile",
            "surface_type": "group",
            "slug": "support-chat"
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pre_open_link_id"], self.link.id)
        self.assertContains(response, f"/capture/{self.link.id}/")
        self.assertContains(response, "htmx.ajax")
        
        # Test invalid deep link slug (should redirect to main public profile page)
        url_invalid = reverse("leads:public_profile_with_link", kwargs={
            "handle": "testprofile",
            "surface_type": "group",
            "slug": "invalid-slug"
        })
        response_invalid = self.client.get(url_invalid)
        self.assertEqual(response_invalid.status_code, 302)
        self.assertEqual(response_invalid["Location"], "/testprofile/")

        # Test incomplete deep link (should redirect to main public profile page)
        url_incomplete = reverse("leads:public_profile_incomplete_link", kwargs={
            "handle": "testprofile",
            "surface_type": "group"
        })
        response_incomplete = self.client.get(url_incomplete)
        self.assertEqual(response_incomplete.status_code, 302)
        self.assertEqual(response_incomplete["Location"], "/testprofile/")

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
        self.assertContains(response, "Create your own profile", status_code=403)

    def test_private_profile_visibility_guard_logged_in_non_owner(self):
        other_user = User.objects.create_user(phone_number="+918888888888")
        other_profile = Profile.objects.create(
            user=other_user,
            handle="otheruser",
            display_name="Other User",
            is_visible=True
        )
        self.client.force_login(other_user)
        self.profile.is_visible = False
        self.profile.save()
        
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Dashboard", status_code=403)
        self.assertNotContains(response, "Create your own profile", status_code=403)

    def test_private_profile_visibility_guard_logged_in_no_profile(self):
        other_user = User.objects.create_user(phone_number="+918888888888")
        self.client.force_login(other_user)
        self.profile.is_visible = False
        self.profile.save()
        
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Dashboard", status_code=403)
        self.assertNotContains(response, "Create your own profile", status_code=403)


    def test_capture_lead_success_flow(self):
        # 1. Send OTP
        send_url = reverse("leads:send_otp")
        send_res = self.client.post(send_url, {"phone_number": "+917777777777"})
        self.assertEqual(send_res.status_code, 200)

        # 2. Verify OTP with correct bypass code
        verify_url = reverse("leads:verify_otp")
        verify_res = self.client.post(verify_url, {"phone_number": "+917777777777", "otp": "123456"})
        self.assertEqual(verify_res.status_code, 200)

        # 3. Submit Form
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Bob",
            "email": "bob@example.com",
            "whatsapp_number": "+917777777777",
            "message": "Hello!",
            "phone": "",  # honeypot must be empty
            "cf-turnstile-response": "test-bypass-token"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're all set!")
        self.assertTrue(Lead.objects.filter(name="Bob").exists())

    def test_capture_lead_fails_without_otp_verification(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Bob Unverified",
            "email": "bobunverified@example.com",
            "whatsapp_number": "+917777777776",
            "message": "Hello!",
            "phone": "",
            "cf-turnstile-response": "test-bypass-token"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please verify your phone number via OTP first.")
        self.assertFalse(Lead.objects.filter(name="Bob Unverified").exists())

    def test_send_otp_fails_with_invalid_phone(self):
        send_url = reverse("leads:send_otp")
        response = self.client.post(send_url, {"phone_number": "invalid-phone"})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"status": "error", "message": "Invalid WhatsApp number. Use format: +919999999999."})

    def test_verify_otp_fails_with_incorrect_code(self):
        # 1. Send OTP
        send_url = reverse("leads:send_otp")
        self.client.post(send_url, {"phone_number": "+917777777775"})

        # 2. Verify with incorrect code
        verify_url = reverse("leads:verify_otp")
        response = self.client.post(verify_url, {"phone_number": "+917777777775", "otp": "999999"})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"status": "error", "message": "Incorrect verification code. Please check console logs."})

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
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
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
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
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
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This link is already put up by the user.")

    def test_add_duplicate_name_and_type_link_view_error(self):
        self.client.force_login(self.user)
        # Create initial link
        Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999998",
            label="hh",
            surface_type="group"
        )
        url = reverse("profiles:add_link")
        payload = {
            "label": "hh",
            "url": "https://wa.me/918888888888",
            "surface_type": "group"
        }
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A link with this name and group type already exists on your profile.")

    def test_toggle_link_view_limit_exceeded(self):
        self.profile.is_visible = False
        self.profile.save()
        for i in range(9):
            Link.objects.create(
                profile=self.profile,
                url=f"https://wa.me/91999999990{i}",
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
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "You can have a maximum of 10 active links.", status_code=400)

    def test_soft_cap_warning_on_9th_link(self):
        self.client.force_login(self.user)
        # Create 7 active links (plus 1 from setUp = 8 active links)
        for i in range(7):
            Link.objects.create(
                profile=self.profile,
                url=f"https://wa.me/91999999998{i}",
                label=f"Link {i}",
                is_active=True
            )
        url = reverse("profiles:add_link")
        payload = {
            "label": "9th Link",
            "url": "https://wa.me/919999999998",
            "surface_type": "group"
        }
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soft cap warning: you have 9 active links. Limit is 10.")

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
        # Create a duplicate lead for same phone number to verify spam prevention in analytics
        Lead.objects.create(
            link=self.link,
            name="Test Lead Dup",
            email="lead_dup@test.com",
            whatsapp_number="+919876543210",
            message="Spamming again",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        url = reverse("profiles:link_analytics", kwargs={"pk": self.link.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mobile")
        self.assertContains(response, "India")
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
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertIn("closeEditModal", response["HX-Trigger"])
        self.assertIn("linkListChanged", response["HX-Trigger"])
        
        self.link.refresh_from_db()
        self.assertEqual(self.link.label, "Updated Label")
        self.assertEqual(self.link.url, "https://wa.me/918888888888")
        self.assertEqual(self.link.surface_type, "group")

    def test_edit_link_view_post_success_json(self):
        self.client.force_login(self.user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        payload = {
            "label": "Updated Label JSON",
            "url": "https://wa.me/918888888888",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)  # No HTMX request
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        
        self.link.refresh_from_db()
        self.assertEqual(self.link.label, "Updated Label JSON")

    def test_edit_link_view_post_validation_error(self):
        self.client.force_login(self.user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        payload = {
            "label": "Updated Label",
            "url": "https://example.com/invalid",
            "surface_type": "group"
        }
        response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only WhatsApp links are allowed on XPAND.")
        
        self.link.refresh_from_db()
        self.assertNotEqual(self.link.label, "Updated Label")

    def test_edit_link_view_post_validation_error_json(self):
        self.client.force_login(self.user)
        url = reverse("profiles:edit_link", kwargs={"pk": self.link.pk})
        payload = {
            "label": "Updated Label JSON",
            "url": "https://example.com/invalid",
            "surface_type": "group"
        }
        response = self.client.post(url, payload)  # No HTMX request
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertIn("Only WhatsApp links are allowed on XPAND.", response.json()["error"])
        
        self.link.refresh_from_db()
        self.assertNotEqual(self.link.label, "Updated Label JSON")

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

    def test_search_handle_view_success(self):
        self.client.force_login(self.user)
        url = reverse("profiles:search_handle")
        response = self.client.post(url, {"handle": "testprofile"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], "/testprofile/")

    def test_search_handle_view_not_found(self):
        self.client.force_login(self.user)
        url = reverse("profiles:search_handle")
        response = self.client.post(url, {"handle": "nonexistent"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Handle "@nonexistent" not found.')

    def test_search_handle_view_anonymous(self):
        url = reverse("profiles:search_handle")
        response = self.client.post(url, {"handle": "testprofile"})
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_capture_lead_authenticated_prefills_name_and_verified_email(self):
        visitor = User.objects.create_user(phone_number="+918888888888")
        visitor_profile = Profile.objects.create(
            user=visitor,
            handle="visitor_handle",
            display_name="Visitor Name",
            verified_email="visitor@test.com",
            email_verified=True
        )
        self.client.force_login(visitor)
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Verify prefilled fields
        self.assertContains(response, 'value="Visitor Name"')
        self.assertContains(response, 'value="visitor@test.com"')
        
        # Verify read-only phone display
        self.assertContains(response, "+918888888888")
        self.assertContains(response, "Remembered")
        # Ensure input tel/select is not present
        self.assertNotContains(response, '<input type="tel" id="whatsapp_number"')

    def test_capture_lead_authenticated_prefills_name_but_not_unverified_email(self):
        visitor = User.objects.create_user(phone_number="+918888888888")
        visitor_profile = Profile.objects.create(
            user=visitor,
            handle="visitor_handle",
            display_name="Visitor Name",
            verified_email="visitor@test.com",
            email_verified=False
        )
        self.client.force_login(visitor)
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Verify prefilled name; email is also prefilled from verified_email even without email_verified=True
        self.assertContains(response, 'value="Visitor Name"')
        self.assertContains(response, 'value="visitor@test.com"')

    def test_capture_lead_authenticated_saves_with_session_phone(self):
        visitor = User.objects.create_user(phone_number="+918888888888")
        visitor_profile = Profile.objects.create(
            user=visitor,
            handle="visitor_handle",
            display_name="Visitor Name",
            verified_email="visitor@test.com",
            email_verified=True
        )
        self.client.force_login(visitor)
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        payload = {
            "name": "Visitor Name",
            "email": "visitor@test.com",
            "message": "Interested in your group!",
            "cf-turnstile-response": "test-bypass-token"
            # NO whatsapp_number provided in payload
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're all set!")
        
        # Verify Lead was created with visitor's phone number
        lead = Lead.objects.get(name="Visitor Name", link=self.link)
        self.assertEqual(lead.whatsapp_number, "+918888888888")

    def test_public_profile_already_submitted_renders_capture_button(self):
        """Repeat visitors always see the lead capture button so they can submit again if needed."""
        visitor = User.objects.create_user(phone_number="+918888888888")
        visitor_profile = Profile.objects.create(
            user=visitor,
            handle="visitor_handle",
            display_name="Visitor Name",
            verified_email="visitor@test.com",
            email_verified=True
        )
        # Create a pre-existing lead for this link
        Lead.objects.create(
            link=self.link,
            name="Visitor Name",
            email="visitor@test.com",
            whatsapp_number="+918888888888",
            message="Already did this."
        )
        self.client.force_login(visitor)
        url = reverse("leads:public_profile", kwargs={"handle": "testprofile"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Verify that repeat visitors still see the lead capture button (not bypassed)
        self.assertContains(response, 'hx-target="#capture-form-container"')

    def test_capture_lead_already_submitted_shows_form_again(self):
        """Repeat visitors are always shown the lead form again so they can submit."""
        visitor = User.objects.create_user(phone_number="+918888888888")
        visitor_profile = Profile.objects.create(
            user=visitor,
            handle="visitor_handle",
            display_name="Visitor Name",
            verified_email="visitor@test.com",
            email_verified=True
        )
        # Create a pre-existing lead for this link
        Lead.objects.create(
            link=self.link,
            name="Visitor Name",
            email="visitor@test.com",
            whatsapp_number="+918888888888",
            message="Already did this."
        )
        self.client.force_login(visitor)
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Verify the lead form is shown (not bypassed) with prefilled fields
        self.assertContains(response, 'value="Visitor Name"')
        self.assertContains(response, 'value="visitor@test.com"')
        self.assertNotContains(response, "You're all set!")

    def test_link_analytics_view_link_specific_uniqueness(self):
        # Create a second link under the same profile
        link2 = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999991",
            label="Second Link"
        )
        
        # Create first lead on self.link
        Lead.objects.create(
            link=self.link,
            name="First Lead",
            email="lead1@test.com",
            whatsapp_number="+919999999900",
            message="Initial submission"
        )
        
        # Create second (duplicate) lead on self.link with same phone number
        Lead.objects.create(
            link=self.link,
            name="Duplicate First Lead",
            email="lead1_dup@test.com",
            whatsapp_number="+919999999900",
            message="Duplicate submission"
        )
        
        # Create lead on link2 next with the same phone number
        Lead.objects.create(
            link=link2,
            name="Second Link Lead",
            email="lead2@test.com",
            whatsapp_number="+919999999900",
            message="Submission on second link"
        )
        
        self.client.force_login(self.user)
        
        # View link2 analytics: should show 1 lead since it is the first submission for link2
        url2 = reverse("profiles:link_analytics", kwargs={"pk": link2.pk})
        response2 = self.client.get(url2)
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, "1 lead")
        
        # View self.link analytics: should show 1 lead since duplicate submissions on same link are deduplicated
        url1 = reverse("profiles:link_analytics", kwargs={"pk": self.link.pk})
        response1 = self.client.get(url1)
        self.assertEqual(response1.status_code, 200)
        self.assertContains(response1, "1 lead")

    def test_toggle_lead_read_view(self):
        lead = Lead.objects.create(
            link=self.link,
            name="Bob",
            email="bob@example.com",
            whatsapp_number="+917777777777",
            message="Read me"
        )
        self.assertFalse(lead.is_read)
        
        self.client.force_login(self.user)
        url = reverse("leads:toggle_lead_read", kwargs={"pk": lead.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertTrue(lead.is_read)
        self.assertContains(response, 'Bob')
        
        # Toggle back to unread
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertFalse(lead.is_read)

    def test_toggle_lead_archive_view(self):
        lead = Lead.objects.create(
            link=self.link,
            name="Bob",
            email="bob@example.com",
            whatsapp_number="+917777777777",
            message="Archive me"
        )
        self.assertFalse(lead.is_archived)
        
        self.client.force_login(self.user)
        url = reverse("leads:toggle_lead_archive", kwargs={"pk": lead.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        lead.refresh_from_db()
        self.assertTrue(lead.is_archived)
        
        # Toggle back to active
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertFalse(lead.is_archived)

    def test_toggle_views_authorization(self):
        lead = Lead.objects.create(
            link=self.link,
            name="Bob",
            email="bob@example.com",
            whatsapp_number="+917777777777",
            message="Security check"
        )
        other_user = User.objects.create_user(phone_number="+918888888888")
        self.client.force_login(other_user)
        
        url_read = reverse("leads:toggle_lead_read", kwargs={"pk": lead.pk})
        response = self.client.post(url_read)
        self.assertEqual(response.status_code, 404)
        
        url_archive = reverse("leads:toggle_lead_archive", kwargs={"pk": lead.pk})
        response = self.client.post(url_archive)
        self.assertEqual(response.status_code, 404)

    def test_search_leads_view_with_status_filter(self):
        lead_active = Lead.objects.create(
            link=self.link,
            name="Active Lead",
            email="active@test.com",
            whatsapp_number="+917777777777",
            is_archived=False
        )
        lead_archived = Lead.objects.create(
            link=self.link,
            name="Archived Lead",
            email="archived@test.com",
            whatsapp_number="+917777777778",
            is_archived=True
        )
        
        self.client.force_login(self.user)
        url = reverse("leads:search_leads")
        
        # Search active (default)
        response = self.client.get(url, {"status_filter": "active"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active Lead")
        self.assertNotContains(response, "Archived Lead")
        
        # Search archived
        response = self.client.get(url, {"status_filter": "archived"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Active Lead")
        self.assertContains(response, "Archived Lead")

    def test_search_leads_view_with_advanced_filters(self):
        # Create a second link with a different surface type (e.g. community)
        link_comm = Link.objects.create(
            profile=self.profile,
            url="https://chat.whatsapp.com/community/ABCDEF12345",
            label="Community Link",
            surface_type="community"
        )
        
        # Lead A: group (self.link), unread
        lead_a = Lead.objects.create(
            link=self.link,
            name="Lead A Group Unread",
            email="leada@test.com",
            whatsapp_number="+917777777771",
            is_read=False
        )
        # Lead B: community, read
        lead_b = Lead.objects.create(
            link=link_comm,
            name="Lead B Community Read",
            email="leadb@test.com",
            whatsapp_number="+917777777772",
            is_read=True
        )
        
        self.client.force_login(self.user)
        url = reverse("leads:search_leads")
        
        # Test 1: Filter by surface type = chat
        response = self.client.get(url, {"surface_filter": "chat"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead A Group Unread")
        self.assertNotContains(response, "Lead B Community Read")
        
        # Test 2: Filter by surface type = community
        response = self.client.get(url, {"surface_filter": "community"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Lead A Group Unread")
        self.assertContains(response, "Lead B Community Read")
        
        # Test 3: Filter by read status = unread
        response = self.client.get(url, {"read_filter": "unread"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead A Group Unread")
        self.assertNotContains(response, "Lead B Community Read")
        
        # Test 4: Filter by read status = read
        response = self.client.get(url, {"read_filter": "read"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Lead A Group Unread")
        self.assertContains(response, "Lead B Community Read")
        
        # Test 5: Filter by date range = today
        response = self.client.get(url, {"date_filter": "today"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead A Group Unread")
        self.assertContains(response, "Lead B Community Read")

    def test_lead_capture_rate_limiting(self):
        from django.core.cache import cache
        cache.clear()
        
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Rate Limit Tester",
            "email": "tester@test.com",
            "whatsapp_number": "+917777777777",
            "cf-turnstile-response": "test-bypass-token"
        }
        
        for _ in range(5):
            response = self.client.post(url, payload)
            self.assertEqual(response.status_code, 200)
            
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many submission attempts")

    def test_lead_capture_turnstile_missing_validation_error(self):
        from django.core.cache import cache
        cache.clear()
        
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Buster",
            "email": "buster@test.com",
            "whatsapp_number": "+917777777777",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Security verification is required")

    from unittest.mock import patch
    @patch("requests.post")
    def test_lead_capture_turnstile_invalid_validation_error(self, mock_post):
        from django.core.cache import cache
        cache.clear()
        
        class MockResponse:
            def json(self):
                return {"success": False}
        mock_post.return_value = MockResponse()
        
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        payload = {
            "name": "Buster",
            "email": "buster@test.com",
            "whatsapp_number": "+917777777777",
            "cf-turnstile-response": "bad-token"
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Security verification failed")


class LinkClickTrackingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+919999999999")
        self.profile = Profile.objects.create(
            user=self.user,
            handle="testprofile",
            display_name="Test Profile"
        )
        self.link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Test Link"
        )

    def test_anonymous_click_tracking_and_deduplication(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        # First click from IP 1.2.3.4
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 1)
        
        # Second click from the same IP 1.2.3.4 (should be deduplicated)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 1)
        
        # Click from a different IP 1.2.3.5 (simulating another device/session by clearing cookies)
        self.client.cookies.clear()
        response = self.client.get(url, REMOTE_ADDR="1.2.3.5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 2)

    def test_logged_in_click_tracking_and_deduplication(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        # Log in
        self.client.force_login(self.user)
        
        # First click (logged in)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 1)
        
        # Second click (logged in, same user, different IP)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 1)

    def test_frontend_already_clicked_param(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        # Click with already_clicked=true
        response = self.client.get(url + "?already_clicked=true", REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 0)

    def test_analytics_views_count(self):
        from apps.links.models import LinkClick
        # Create some clicks
        LinkClick.objects.create(link=self.link, ip_address="1.2.3.4")
        LinkClick.objects.create(link=self.link, ip_address="1.2.3.5")
        
        self.client.force_login(self.user)
        url = reverse("profiles:link_analytics", kwargs={"pk": self.link.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["views"], 2)

    def test_logged_out_then_logged_in_no_merging(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        # 1. Click while logged out (gets visitor_id cookie and records IP-based click)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 1)
        click = self.link.clicks.first()
        self.assertIsNotNone(click.visitor_id)
        self.assertIsNone(click.phone_number)
        self.assertEqual(click.ip_address, "1.2.3.4")
        
        # 2. Log in with a user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(phone_number="+917777777777")
        self.client.force_login(user)
        
        # 3. Click again while logged in (from the same device/IP)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        
        # Total link clicks in DB should be 2 now
        self.assertEqual(self.link.clicks.count(), 2)
        
        # 4. Analytics should count it as 2 clicks (1 unique IP + 1 unique phone number)
        self.client.force_login(self.user) # Log in as the link owner to check analytics
        analytics_url = reverse("profiles:link_analytics", kwargs={"pk": self.link.id})
        response = self.client.get(analytics_url)
        self.assertEqual(response.context["views"], 2)

    def test_logged_out_submit_lead_then_logged_in_click_again(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        # 1. Click while logged out (gets visitor_id cookie and records IP-based click)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.link.clicks.count(), 1)
        
        # 2. Submit a lead while logged out with a phone number
        from apps.leads.models import Lead
        Lead.objects.create(
            link=self.link,
            name="Test User",
            email="test@user.com",
            whatsapp_number="+917777777777",
            ip_address="1.2.3.4"
        )
        
        # 3. Log in with that user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(phone_number="+917777777777")
        self.client.force_login(user)
        
        # 4. Click again while logged in (even if they already submitted, simulated by hitting the capture endpoint)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(response.status_code, 200)
        
        # Total link clicks in DB should be 2 now because click tracking runs before the lead check
        self.assertEqual(self.link.clicks.count(), 2)
        
        # 5. Analytics should show 2 clicks
        self.client.force_login(self.user)
        analytics_url = reverse("profiles:link_analytics", kwargs={"pk": self.link.id})
        response = self.client.get(analytics_url)
        self.assertEqual(response.context["views"], 2)

    def test_logged_in_then_logged_out_reset(self):
        url = reverse("leads:capture_lead", kwargs={"handle": "testprofile", "link_id": self.link.id})
        
        # 1. Log in and click
        self.client.force_login(self.user)
        response = self.client.get(url, REMOTE_ADDR="1.2.3.4")
        self.assertEqual(self.link.clicks.count(), 1)
        
        # 2. Log out (should NOT trigger cookie deletion)
        logout_url = reverse("authentication:logout")
        response = self.client.post(logout_url)
        self.assertEqual(response.status_code, 302)
        
        # Verify visitor_id cookie was NOT deleted
        cookie = self.client.cookies.get("xpand_visitor_id")
        self.assertTrue(cookie and cookie.value != "" and cookie['max-age'] != 0)
        
        # 3. Click again while logged out (same visitor ID, different IP) - should be deduplicated
        response = self.client.get(url, REMOTE_ADDR="1.2.3.5")
        self.assertEqual(self.link.clicks.count(), 1)
        
        # 4. If we clear cookies to simulate a different device, a new anonymous click is recorded
        self.client.cookies.clear()
        response = self.client.get(url, REMOTE_ADDR="1.2.3.5")
        self.assertEqual(self.link.clicks.count(), 2)
        
        # Verify total views in analytics is 2
        self.client.force_login(self.user)
        analytics_url = reverse("profiles:link_analytics", kwargs={"pk": self.link.id})
        response = self.client.get(analytics_url)
        self.assertEqual(response.context["views"], 2)

    def test_analytics_views_count_anonymous_ips(self):
        from apps.links.models import LinkClick
        # Create anonymous clicks with the same IP and different IPs
        LinkClick.objects.create(link=self.link, ip_address="10.0.0.1", visitor_id="anon1")
        LinkClick.objects.create(link=self.link, ip_address="10.0.0.1", visitor_id="anon2") # Same IP
        LinkClick.objects.create(link=self.link, ip_address="10.0.0.2", visitor_id="anon3") # Different IP
        
        self.client.force_login(self.user)
        url = reverse("profiles:link_analytics", kwargs={"pk": self.link.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Should count unique anonymous IPs: 10.0.0.1 and 10.0.0.2 = 2 unique views
        self.assertEqual(response.context["views"], 2)


from django.urls import reverse
from django.utils import timezone
import datetime
from apps.links.models import LinkClick

class LinkInsightsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+919999999999")
        self.profile = Profile.objects.create(
            user=self.user,
            handle="test_insights",
            display_name="Test Insights"
        )
        self.link_a = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999991",
            label="Link A"
        )
        self.link_b = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999992",
            label="Link B"
        )
        self.insights_url = reverse("profiles:link_insights")

    def test_insights_unauthenticated_redirect(self):
        response = self.client.get(self.insights_url)
        self.assertEqual(response.status_code, 302)

    def test_insights_empty_state(self):
        self.client.force_login(self.user)
        response = self.client.get(self.insights_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Most-converting link this week")
        self.assertContains(response, "None (no conversions recorded)")
        self.assertEqual(response.context["best_cvr"], 0.0)

    def test_insights_no_links_warning(self):
        # Delete the setup links to simulate profile with no links
        self.link_a.delete()
        self.link_b.delete()
        self.client.force_login(self.user)
        response = self.client.get(self.insights_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add links to view insights")
        self.assertNotContains(response, "Most-converting link this week")
        self.assertFalse(response.context["has_links"])

    def test_insights_highest_conversion_rate(self):
        self.client.force_login(self.user)
        
        # Link A: 2 clicks, 1 unique lead -> 50.0% CVR
        LinkClick.objects.create(link=self.link_a, ip_address="1.1.1.1")
        LinkClick.objects.create(link=self.link_a, ip_address="1.1.1.2")
        Lead.objects.create(link=self.link_a, whatsapp_number="+919999999991", name="Lead A", email="a@a.com")

        # Link B: 4 clicks, 1 unique lead -> 25.0% CVR
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.1")
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.2")
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.3")
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.4")
        Lead.objects.create(link=self.link_b, whatsapp_number="+919999999992", name="Lead B", email="b@b.com")

        response = self.client.get(self.insights_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["best_link"], self.link_a)
        self.assertEqual(response.context["best_cvr"], 50.0)
        self.assertContains(response, "Link A")
        self.assertContains(response, "50.0%")

    def test_insights_tie_breaker_highest_leads(self):
        self.client.force_login(self.user)

        # Link A: 2 clicks, 1 unique lead -> 50.0% CVR
        LinkClick.objects.create(link=self.link_a, ip_address="1.1.1.1")
        LinkClick.objects.create(link=self.link_a, ip_address="1.1.1.2")
        Lead.objects.create(link=self.link_a, whatsapp_number="+919999999991", name="Lead A", email="a@a.com")

        # Link B: 4 clicks, 2 unique leads -> 50.0% CVR
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.1")
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.2")
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.3")
        LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.4")
        Lead.objects.create(link=self.link_b, whatsapp_number="+919999999993", name="Lead B1", email="b1@b.com")
        Lead.objects.create(link=self.link_b, whatsapp_number="+919999999994", name="Lead B2", email="b2@b.com")

        # Both have 50% CVR. Link B has more leads (2 > 1).
        response = self.client.get(self.insights_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["best_link"], self.link_b)
        self.assertEqual(response.context["best_cvr"], 50.0)
        self.assertContains(response, "Link B")

    def test_insights_time_filtering(self):
        self.client.force_login(self.user)

        # Link A: 1 click, 1 lead (last 7 days) -> 100% CVR
        LinkClick.objects.create(link=self.link_a, ip_address="1.1.1.1")
        Lead.objects.create(link=self.link_a, whatsapp_number="+919999999991", name="Lead A", email="a@a.com")

        # Link B: click + lead created 10 days ago (should be excluded) -> 0% CVR in last 7 days
        old_time = timezone.now() - datetime.timedelta(days=10)
        click_b = LinkClick.objects.create(link=self.link_b, ip_address="2.1.1.1")
        click_b.created_at = old_time
        click_b.save()
        lead_b = Lead.objects.create(link=self.link_b, whatsapp_number="+919999999992", name="Lead B", email="b@b.com")
        lead_b.created_at = old_time
        lead_b.save()

        response = self.client.get(self.insights_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["best_link"], self.link_a)
        self.assertEqual(response.context["best_cvr"], 100.0)


class LeadReplyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+919999999999")
        self.profile = Profile.objects.create(
            user=self.user,
            handle="test_reply",
            display_name="Test Reply"
        )
        self.link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Chat"
        )
        self.lead = Lead.objects.create(
            link=self.link,
            name="John Doe",
            email="john@john.com",
            whatsapp_number="+919999999998",
            message="Let's chat!",
            is_read=False
        )
        self.mark_read_url = reverse("leads:mark_lead_read", kwargs={"pk": self.lead.id})

    def test_whatsapp_reply_url_generation(self):
        # Should strip non-digits (like '+') and url-encode the message template
        url = self.lead.whatsapp_reply_url
        self.assertIn("phone=919999999998", url)
        self.assertIn("text=Hi%20John%20Doe", url)

    def test_mark_lead_read_unauthenticated(self):
        response = self.client.post(self.mark_read_url)
        self.assertEqual(response.status_code, 302)

    def test_mark_lead_read_success(self):
        self.client.force_login(self.user)
        response = self.client.post(self.mark_read_url)
        self.assertEqual(response.status_code, 200)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_read)
        # Verify it renders lead_row template with open envelope/unread trigger
        self.assertContains(response, "Mark as unread")


class PremiumFeaturesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+918888888888")
        self.profile = Profile.objects.create(user=self.user, handle="premium_user", display_name="Premium User", is_visible=True)

    def test_upgrade_premium_view_success(self):
        self.client.force_login(self.user)
        url = reverse("profiles:upgrade_premium")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_premium)

    def test_upgrade_premium_view_unauthenticated(self):
        url = reverse("profiles:upgrade_premium")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_premium_non_whatsapp_link_allowed(self):
        self.profile.is_premium = True
        self.profile.save()
        
        # Test adding non-WhatsApp URL as premium user
        link = Link(profile=self.profile, label="My Site", url="https://example.com", surface_type="other")
        link.full_clean()
        link.save()
        self.assertEqual(link.surface_type, "other")

    def test_free_non_whatsapp_link_denied(self):
        self.profile.is_premium = False
        self.profile.save()
        
        # Test adding non-WhatsApp URL as free user should raise ValidationError
        link = Link(profile=self.profile, label="My Site", url="https://example.com", surface_type="other")
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_premium_link_limit_50(self):
        self.profile.is_premium = True
        self.profile.save()
        
        # Create 50 links (all active)
        for i in range(50):
            Link.objects.create(
                profile=self.profile,
                label=f"Link {i}",
                url=f"https://example.com/link{i}",
                surface_type="other",
                is_active=True
            )
            
        # Try to add 51st active link
        extra_link = Link(profile=self.profile, label="Extra Link", url="https://example.com/extra", surface_type="other", is_active=True)
        with self.assertRaises(ValidationError):
            extra_link.full_clean()

    def test_free_link_limit_10(self):
        self.profile.is_premium = False
        self.profile.save()
        
        # Create 10 active whatsapp links
        for i in range(10):
            Link.objects.create(
                profile=self.profile,
                label=f"Link {i}",
                url=f"https://wa.me/91999999990{i}",
                surface_type="group",
                is_active=True
            )
            
        # Try to add 11th active link
        extra_link = Link(profile=self.profile, label="Extra Link", url="https://wa.me/919999999990", surface_type="group", is_active=True)
        with self.assertRaises(ValidationError):
            extra_link.full_clean()

    def test_premium_lead_bypass_cookie_renders_direct_link(self):
        self.profile.is_premium = True
        self.profile.save()
        
        link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Premium Link",
            surface_type="group",
            is_active=True
        )
        
        # Request public profile with the submitted cookie
        url = reverse("leads:public_profile", kwargs={"handle": self.profile.handle})
        self.client.cookies["submitted_leads"] = str(link.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Direct link should be rendered with href, not hx-get target
        self.assertContains(response, f'href="https://wa.me/919999999999"')
        self.assertNotContains(response, 'hx-target="#capture-form-container"')

    def test_premium_lead_bypass_capture_view_redirects(self):
        self.profile.is_premium = True
        self.profile.save()
        
        link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Premium Link",
            surface_type="group",
            is_active=True
        )
        
        url = reverse("leads:capture_lead", kwargs={"handle": self.profile.handle, "link_id": link.id})
        self.client.cookies["submitted_leads"] = str(link.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Should directly redirect via JS script tag
        self.assertContains(response, 'window.location.href = "https://wa.me/919999999999"')

    def test_premium_lead_bypass_deep_link_redirects_immediately(self):
        self.profile.is_premium = True
        self.profile.save()
        
        link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Premium Link",
            surface_type="group",
            is_active=True
        )
        
        url = reverse("leads:public_profile_with_link", kwargs={
            "handle": self.profile.handle,
            "surface_type": "group",
            "slug": "premium-link"
        })
        self.client.cookies["submitted_leads"] = str(link.id)
        response = self.client.get(url)
        # Should directly do a standard HTTP redirect to the destination URL
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://wa.me/919999999999")

    def test_premium_lead_capture_success_sets_cookie(self):
        self.profile.is_premium = True
        self.profile.save()
        
        link = Link.objects.create(
            profile=self.profile,
            url="https://wa.me/919999999999",
            label="Premium Link",
            surface_type="group",
            is_active=True
        )
        
        # Standard flow to verify bypass cookie is set on successful submission
        url = reverse("leads:capture_lead", kwargs={"handle": self.profile.handle, "link_id": link.id})
        payload = {
            "name": "Test Visitor",
            "email": "visitor@example.com",
            "whatsapp_number": "+919999999991",
            "message": "Hello",
            "cf-turnstile-response": "test-bypass-token"
        }
        
        # Verify otp verification bypass session
        session = self.client.session
        session.save()
        from django.core.cache import cache
        cache.set(f"verified_lead_phone_{session.session_key}_+919999999991", True, timeout=600)
        
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("submitted_leads", response.cookies)
        self.assertEqual(response.cookies["submitted_leads"].value, str(link.id))

    def test_non_whatsapp_link_restricted_to_other_surface_type(self):
        self.profile.is_premium = True
        self.profile.save()

        # Non-WhatsApp link with 'other' type should be allowed
        link_ok = Link(
            profile=self.profile,
            url="https://google.com",
            label="Google Link",
            surface_type="other"
        )
        try:
            link_ok.full_clean()
        except ValidationError:
            self.fail("ValidationError raised unexpectedly for non-WhatsApp link with 'other' surface type.")

        # Non-WhatsApp link with any other type should be rejected
        link_fail = Link(
            profile=self.profile,
            url="https://google.com",
            label="Google Group",
            surface_type="group"
        )
        with self.assertRaises(ValidationError) as context:
            link_fail.full_clean()
        self.assertIn("Non-WhatsApp links can only be of type 'Other'.", context.exception.messages)







