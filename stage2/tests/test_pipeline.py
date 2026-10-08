"""Offline regression checks; no running CARLA server is required."""
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import cv2
import numpy as np
from PIL import Image

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE))
import record_2stage as capture
import equi_extract_for_fov100_multiprocess as stitch
import stage2vis_rgbd2video as video


def make_recording(root, frames=(100, 102), segmentation=True):
    for index, view in enumerate(stitch.VIEWS):
        rgb = root / f'rgb_{view}_fov120'
        depth = root / f'depth_npy_{view}_fov_120'
        seg = root / f'segmentation_{view}_fov120'
        rgb.mkdir(parents=True)
        depth.mkdir()
        if segmentation:
            seg.mkdir()
        for frame in frames:
            Image.fromarray(np.full((16, 16, 3), 30 * (index + 1), dtype=np.uint8)).save(rgb / f'{frame:06d}.png')
            np.save(depth / f'{frame:06d}.npy', np.full((16, 16), 5.0, dtype=np.float32))
            if segmentation:
                Image.fromarray(np.full((16, 16), index + 1, dtype=np.uint8)).save(seg / f'{frame:06d}.png')


class PipelineTests(unittest.TestCase):
    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(STAGE / name), *map(str, args)],
                              cwd='/tmp', text=True, capture_output=True, timeout=90)

    def test_complete_pipeline_and_resume(self):
        with tempfile.TemporaryDirectory(prefix='pano test ') as temp:
            root = Path(temp)
            make_recording(root)
            (root / 'route_collision_log.csv').write_text('frame_id,x,y,z,yaw\n102,0,0,5,0\n')
            (root / 'route_pose_log.csv').write_text('frame_id,x,y,z,yaw\n100,0,0,5,0\n102,0,0,6,0\n')
            args = ('--base_dirs', root, '--original_fov', 120, '--equi_height', 16,
                    '--equi_width', 32, '--num_process', 2, '--fps', 20)
            result = self.run_script('run_stage2_stitch_and_vis.py', *args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            depth = np.load(root / 'panorama_depth_npy/000100.npy')
            self.assertEqual(depth.shape, (16, 32))
            self.assertTrue(np.isfinite(depth).all())
            self.assertTrue((depth > 0).all())
            labels = np.asarray(Image.open(root / 'panorama_segmentation/000100.png'))
            self.assertEqual(set(np.unique(labels)), set(range(1, 7)))
            output = root / f'{root.name}_PanoVideo.mp4'
            reader = cv2.VideoCapture(str(output))
            try:
                self.assertEqual(int(reader.get(cv2.CAP_PROP_FRAME_COUNT)), 2)
                self.assertEqual(int(reader.get(cv2.CAP_PROP_FPS)), 20)
                ok, frame = reader.read()
                self.assertTrue(ok)
                self.assertEqual(frame.shape, (32, 32, 3))
            finally:
                reader.release()
            rgb = root / 'panorama_rgb/000100.png'
            original_mtime = rgb.stat().st_mtime_ns
            result = self.run_script('run_stage2_stitch_and_vis.py', *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(rgb.stat().st_mtime_ns, original_mtime)
            # A missing visualization must be regenerated even when NPY/RGB exist.
            (root / 'panorama_depth_visual/000100.png').unlink()
            result = self.run_script('run_stage2_stitch_and_vis.py', *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / 'panorama_depth_visual/000100.png').is_file())

    def test_rgbd_without_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_recording(root, segmentation=False)
            result = self.run_script('equi_extract_for_fov100_multiprocess.py',
                                     '--base_dir', root, '--original_fov', 120,
                                     '--equi_height', 16, '--equi_width', 32, '--num_process', 1)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / 'panorama_depth_npy/000100.npy').exists())
            self.assertFalse((root / 'panorama_segmentation').exists())

    def test_missing_view_frame_stops_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_recording(root)
            (root / 'depth_npy_left_fov_120/000100.npy').unlink()
            result = self.run_script('run_stage2_stitch_and_vis.py', '--base_dirs', root,
                                     '--original_fov', 120, '--equi_height', 16, '--equi_width', 32)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Frame IDs do not match', result.stderr)
            self.assertFalse(list(root.glob('*.mp4')))

    def test_bad_depth_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_recording(root)
            np.save(root / 'depth_npy_left_fov_120/000100.npy', np.full((16, 16), np.nan))
            result = self.run_script('equi_extract_for_fov100_multiprocess.py', '--base_dir', root,
                                     '--original_fov', 120, '--equi_height', 16, '--equi_width', 32,
                                     '--num_process', 1)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid depth', result.stderr)

    def test_video_rejects_equal_counts_with_different_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'panorama_rgb').mkdir()
            (root / 'panorama_depth_visual').mkdir()
            (root / 'panorama_rgb/000001.png').touch()
            (root / 'panorama_depth_visual/000002.png').touch()
            with self.assertRaisesRegex(ValueError, 'frame IDs'):
                video.paired_frames(root)

    def test_capture_resume_detects_interior_hole(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_recording(root, frames=(100, 102, 105))
            self.assertEqual(capture.saved_prefix(root, [100, 102, 105], 120), 3)
            (root / 'rgb_front_fov120/000102.png').unlink()
            self.assertEqual(capture.saved_prefix(root, [100, 102, 105], 120), 1)

    def test_capture_discards_stale_sensor_callbacks(self):
        callbacks = queue.Queue()
        callbacks.put(SimpleNamespace(frame=8))
        callbacks.put(SimpleNamespace(frame=9))
        self.assertEqual(capture.receive_frame(callbacks, 9).frame, 9)
        callbacks.put(SimpleNamespace(frame=11))
        with self.assertRaisesRegex(RuntimeError, 'skipped'):
            capture.receive_frame(callbacks, 10)

    def test_narrow_dynamic_height_range_terminates(self):
        manager = capture.DynamicHeightManager(initial_height=2.5, min_height=2, max_height=3)
        heights = [manager.get_current_height() for _ in range(300)]
        self.assertTrue(all(2 <= h <= 3 for h in heights))

    def test_absolute_dynamic_combination_rejected_without_server(self):
        result = self.run_script('record_2stage.py', '--csv_path', 'missing.csv',
                                 '--map', 'Town05', '--height_mode', 'absolute', '--dynamic_height')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--dynamic_height requires', result.stderr)


if __name__ == '__main__':
    unittest.main()
