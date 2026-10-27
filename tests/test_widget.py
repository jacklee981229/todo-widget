import unittest

from widget import ACCENT, BG, PROJECT_COLOURS, contrast, ease_frames, ink, project_colour, spring_frames, tint


class ProjectColourTest(unittest.TestCase):
    def test_a_project_keeps_its_colour(self):
        self.assertEqual(project_colour("jacks-space"), project_colour("jacks-space"))
        self.assertIn(project_colour("Jack"), PROJECT_COLOURS)

    def test_every_project_name_reads_on_its_chip_and_on_the_widget(self):
        for colour in PROJECT_COLOURS:
            self.assertGreaterEqual(contrast(colour, tint(colour)), 4.5, colour)
            self.assertGreaterEqual(contrast(colour, BG), 4.5, colour)


class InkTest(unittest.TestCase):
    def test_dark_ink_on_yellow_and_light_ink_on_indigo(self):
        self.assertEqual(ink("#ffd60a"), BG)
        self.assertEqual(ink("#5e5ce6"), "#ffffff")

    def test_the_accent_reads_at_least_4_5_to_1(self):
        self.assertGreaterEqual(contrast(ink(ACCENT), ACCENT), 4.5)
        self.assertGreaterEqual(contrast(ACCENT, BG), 4.5)

    def test_contrast_matches_wcag_black_on_white(self):
        self.assertAlmostEqual(contrast("#000000", "#ffffff"), 21)


class FramesTest(unittest.TestCase):
    def test_the_tick_bounces_a_little_and_lands_on_the_box(self):
        frames = spring_frames(0.7, 1, 520, 12, 420)
        self.assertLess(frames[0], 0.8)
        self.assertTrue(1.05 < max(frames) < 1.25)  # one small overshoot, inside the picture's margin
        self.assertEqual(frames[-1], 1)

    def test_untick_shrinks_steadily_to_nothing(self):
        frames = ease_frames(1, 0, 140)
        self.assertEqual(frames, sorted(frames, reverse=True))
        self.assertEqual(frames[-1], 0)


if __name__ == "__main__":
    unittest.main()
