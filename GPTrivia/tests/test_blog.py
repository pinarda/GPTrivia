from django.test import TestCase
from django.urls import reverse


class BlogPostViewTests(TestCase):
    def test_roboalex_blog_page_renders(self):
        response = self.client.get(reverse("blog_roboalex"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "roboAlex 1.0")
        self.assertContains(response, "May 17, 2021")
        self.assertContains(response, "The original post used an interactive Plotly heatmap here.")
        self.assertContains(response, "unnamed-chunk-11-1.png")
