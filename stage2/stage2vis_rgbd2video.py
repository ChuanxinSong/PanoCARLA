"""Create an RGB-over-depth MP4, with collision and world-Z annotations."""
import argparse
from pathlib import Path

import cv2
import pandas as pd
from tqdm import tqdm


def paired_frames(base_dir):
    root = Path(base_dir)
    rgb = {path.stem: path for path in (root / 'panorama_rgb').glob('*.png')}
    depth = {path.stem: path for path in (root / 'panorama_depth_visual').glob('*.png')}
    if not rgb or rgb.keys() != depth.keys():
        raise ValueError('RGB and depth must have the same nonempty set of frame IDs')
    return [(frame, rgb[frame], depth[frame]) for frame in sorted(rgb, key=int)]


def read_log(root, suffix):
    paths = list(root.glob(f'*{suffix}'))
    if len(paths) > 1:
        raise ValueError(f'Ambiguous logs matching *{suffix} in {root}')
    return pd.read_csv(paths[0]) if paths else None


def create_video(base_dir, fps):
    if fps <= 0:
        raise ValueError('FPS must be positive')
    root = Path(base_dir).resolve()
    frames = paired_frames(root)
    collision_log = read_log(root, '_collision_log.csv')
    collision_frames = set(collision_log.frame_id.astype(int)) if collision_log is not None else set()
    pose_log = read_log(root, '_pose_log.csv')
    pose_z = dict(zip(pose_log.frame_id.astype(int), pose_log.z)) if pose_log is not None else {}
    output = root / f'{root.name}_PanoVideo.mp4'
    temporary = root / f'{root.name}_PanoVideo.partial.mp4'
    writer = None
    expected_shape = None
    try:
        for frame, rgb_path, depth_path in tqdm(frames, desc='Video'):
            rgb = cv2.imread(str(rgb_path))
            depth = cv2.imread(str(depth_path))
            if rgb is None or depth is None or rgb.shape != depth.shape:
                raise ValueError(f'Unreadable or mismatched images at frame {frame}')
            combined = cv2.vconcat([rgb, depth])
            if writer is None:
                expected_shape = combined.shape
                height, width = combined.shape[:2]
                writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
                if not writer.isOpened():
                    raise RuntimeError('OpenCV could not open the MP4 encoder')
            elif combined.shape != expected_shape:
                raise ValueError(f'Video frame dimensions changed at frame {frame}')
            if int(frame) in collision_frames:
                cv2.putText(combined, f'Frame: {frame} - COLLISION!', (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3, cv2.LINE_AA)
            if int(frame) in pose_z:
                cv2.putText(combined, f'World Z: {pose_z[int(frame)]:.2f} m',
                            (30, combined.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX,
                            1.2, (0, 255, 0), 2, cv2.LINE_AA)
            writer.write(combined)
        writer.release()
        writer = None
        temporary.replace(output)
    finally:
        if writer is not None:
            writer.release()
        temporary.unlink(missing_ok=True)
    print(f'Saved: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base_dir', required=True)
    parser.add_argument('--fps', type=int, default=20)
    args = parser.parse_args()
    create_video(args.base_dir, args.fps)
