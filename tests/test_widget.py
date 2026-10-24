import unittest
from datetime import date

from widget import BG, RAINBOW, contrast, day_colour, ease_frames, ink, spring_frames


class DayColourTest(unittest.TestCase):
    def test_a_week_goes_round_the_rainbow_from_monday(self):
        week = [day_colour(date(2026, 10, 19 + i)) for i in range(7)]  # Monday 19 Oct to Sunday 25 Oct
        self.assertEqual(week, list(RAINBOW))

    def test_next_monday_starts_again(self):
        self.assertEqual(day_colour(date(2026, 10, 26)), RAINBOW[0])


class InkTest(unittest.TestCase):
    def test_dark_ink_on_yellow_and_light_ink_on_indigo(self):
        self.assertEqual(ink("#ffd60a"), BG)
        self.assertEqual(ink("#5e5ce6"), "#ffffff")

    def test_every_day_reads_at_least_4_5_to_1(self):
        for colour in RAINBOW:
            self.assertGreaterEqual(contrast(ink(colour), colour), 4.5, colour)

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
