from django.test import TestCase
from django.urls import reverse


class CorePagesTests(TestCase):
    def test_homepage_status_code(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

    def test_about_page_status_code(self):
        response = self.client.get(reverse('core:about'))
        self.assertEqual(response.status_code, 200)

    def test_how_it_works_page_status_code(self):
        response = self.client.get(reverse('core:how_it_works'))
        self.assertEqual(response.status_code, 200)

    def test_safety_page_status_code(self):
        response = self.client.get(reverse('core:safety'))
        self.assertEqual(response.status_code, 200)

    def test_contact_page_status_code(self):
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)
