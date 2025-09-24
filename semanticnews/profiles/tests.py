from datetime import timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from semanticnews.agenda.models import Event
from semanticnews.topics.models import Topic

class UserListViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", "alice@example.com", "password")
        self.bob = User.objects.create_user("bob", "bob@example.com", "password", is_active=False)

    def test_lists_active_users(self):
        Topic.objects.create(title="Alice Topic", created_by=self.alice, status="published")

        response = self.client.get(reverse("user_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alice.username)
        self.assertNotContains(response, self.bob.username)

    def test_orders_users_by_recent_activity(self):
        Topic.objects.create(title="Old", created_by=self.alice, status="published")
        Topic.objects.create(title="New", created_by=self.alice, status="published")
        # Simulate older activity for Alice
        Topic.objects.filter(created_by=self.alice).update(
            updated_at=timezone.now() - timedelta(days=2)
        )

        carol = get_user_model().objects.create_user("carol", "carol@example.com", "password")
        Event.objects.create(title="Fresh Event", date="2024-01-01", status="published", created_by=carol)

        response = self.client.get(reverse("user_list"))

        users = list(response.context["users"])
        self.assertEqual(users[0].username, "carol")
