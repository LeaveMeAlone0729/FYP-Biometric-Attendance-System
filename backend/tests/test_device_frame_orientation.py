"""Captured JPEG orientation is normalized by existing decode, not UI transforms."""
import io
import sys
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.biometrics.inference import Biometrics


class DeviceFrameOrientationTests(unittest.TestCase):
    def test_all_jpeg_exif_orientations_are_upright_before_inference(self):
        upright=Image.new('RGB',(160,120))
        colors=((240,20,20),(20,240,20),(20,20,240),(240,240,20))
        for box,color in zip(((0,0,80,60),(80,0,160,60),(0,60,80,120),(80,60,160,120)),colors):
            upright.paste(color,box)
        inverse={1:None,2:Image.Transpose.FLIP_LEFT_RIGHT,3:Image.Transpose.ROTATE_180,
            4:Image.Transpose.FLIP_TOP_BOTTOM,5:Image.Transpose.TRANSPOSE,
            6:Image.Transpose.ROTATE_90,7:Image.Transpose.TRANSVERSE,8:Image.Transpose.ROTATE_270}
        detector=Biometrics()
        try:
            for orientation,transform in inverse.items():
                with self.subTest(exif_orientation=orientation):
                    pixels=upright.copy() if transform is None else upright.transpose(transform)
                    exif=Image.Exif();exif[274]=orientation
                    encoded=io.BytesIO();pixels.save(encoded,format='JPEG',quality=95,subsampling=0,exif=exif)
                    decoded=detector.decode(encoded.getvalue())
                    self.assertEqual(decoded.shape,(120,160,3))
                    for (x,y),expected in zip(((40,30),(120,30),(40,90),(120,90)),colors):
                        self.assertLess(np.abs(decoded[y,x].astype(int)-np.array(expected)).max(),8)
        finally:detector.close()
