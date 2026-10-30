import sys
from pathlib import Path
SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import os
import unittest
try:
    import cv2
    import numpy as np
    import ddddocr
    from reward_vision import challenge_number_image, read_challenge_number, read_result_number
    HAVE_VISION_DEPS = True
except ImportError:
    HAVE_VISION_DEPS = False


@unittest.skipUnless(HAVE_VISION_DEPS, 'Vision dependencies (cv2, numpy, ddddocr) not installed')
class RewardVisionTests(unittest.TestCase):
    def test_wallet_object_does_not_expand_number_crop(self):
        image = np.zeros((300, 500, 3), dtype=np.uint8)
        yellow = (0, 220, 255)
        cv2.putText(image, '800', (70, 75), cv2.FONT_HERSHEY_SIMPLEX, 2, yellow, 5)
        without_wallet = challenge_number_image(image, (0, 0, 500, 300))
        cv2.circle(image, (220, 210), 20, yellow, -1)
        with_wallet = challenge_number_image(image, (0, 0, 500, 300))
        np.testing.assert_array_equal(with_wallet, without_wallet)

    def test_read_result_number_digit_translation(self):
        from unittest.mock import MagicMock
        mock_ocr = MagicMock()
        mock_ocr.classification.return_value = "16O0"
        image = np.zeros((300, 500, 3), dtype=np.uint8)
        cv2.putText(image, '1600', (70, 75), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 200, 0), 5)
        res = read_result_number(image, (0, 0, 500, 300), mock_ocr)
        self.assertEqual(res, 1600)

        # Test with 'S', 'B', 'I'
        mock_ocr.classification.return_value = "SB1O"
        res2 = read_result_number(image, (0, 0, 500, 300), mock_ocr)
        self.assertEqual(res2, 5810)

    def test_binary_digit_mask_cache_hits_on_identical_bitmap(self):
        class DummyOcr:
            def __init__(self, reply: str):
                self.reply = reply
                self.calls = 0

            def classification(self, _data: bytes) -> str:
                self.calls += 1
                return self.reply

        image = np.zeros((300, 500, 3), dtype=np.uint8)
        cv2.putText(image, '1600', (70, 75), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 200, 0), 5)
        real_like_ocr = DummyOcr("1600")
        self.assertEqual(read_result_number(image, (0, 0, 500, 300), real_like_ocr), 1600)
        self.assertEqual(read_result_number(image, (0, 0, 500, 300), real_like_ocr), 1600)
        self.assertEqual(real_like_ocr.calls, 1)

    @unittest.skipUnless(os.environ.get('HOLOLIVE_TEST_VIDEO'), 'Private video is optional and not distributed')
    def test_video_challenge_reads_800(self):
        capture = cv2.VideoCapture(os.environ['HOLOLIVE_TEST_VIDEO'])
        ocr = ddddocr.DdddOcr(show_ad=False)
        try:
            for seconds in (335.5, 336.0, 336.5):
                capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
                ok, frame = capture.read()
                self.assertTrue(ok)
                frame = cv2.resize(frame[163:862, 517:1759], (1920, 1080), interpolation=cv2.INTER_CUBIC)
                self.assertEqual(read_challenge_number(frame, (606, 389, 870, 253), ocr), 800)
        finally:
            capture.release()


if __name__ == '__main__':
    unittest.main()
