from django.test import TestCase
from django.urls import reverse


class BlogPostViewTests(TestCase):
    def test_blog_index_renders_all_posts(self):
        response = self.client.get(reverse("blog_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TriviaStats Archive")
        self.assertContains(response, "roboAlex 1.0")
        self.assertContains(response, "Joker Stats")
        self.assertContains(response, "Other Trivia Plots")

    def test_roboalex_blog_page_renders(self):
        response = self.client.get(reverse("blog_roboalex"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "roboAlex 1.0")
        self.assertContains(response, "May 17, 2021")
        self.assertContains(response, "The original post used an interactive Plotly heatmap here.")
        self.assertContains(response, "unnamed-chunk-11-1.png")

    def test_joker_stats_blog_page_renders(self):
        response = self.client.get(reverse("blog_joker_stats"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Joker Stats")
        self.assertContains(response, "September 9, 2020")
        self.assertContains(response, "The original post used interactive Plotly heatmaps")
        self.assertContains(response, "unnamed-chunk-8-10.png")

    def test_other_trivia_plots_blog_page_renders(self):
        response = self.client.get(reverse("blog_other_trivia_plots"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Other Trivia Plots")
        self.assertContains(response, "August 18, 2020")
        self.assertContains(response, "interactive Plotly widgets")
        self.assertContains(response, "unnamed-chunk-8-10.png")
