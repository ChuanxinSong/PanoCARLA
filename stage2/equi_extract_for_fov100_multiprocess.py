"""Stitch six square perspective views into RGB-D and optional label panoramas."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import os
import cv2
from tqdm import tqdm
import multiprocessing
from einops import repeat

# Use the exact projection runtime bundled with this repository.
sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor' / 'equilib'))
from equilib.pers2equi.base import pers2equi
import py360convert

# Camera orientations in radians, matching the recording rig.
VIEWS = ["front", "back", "left", "right", "up", "down"]
ROTATIONS = {
    "front": {'roll': 0., 'pitch': 0., 'yaw': 0.},
    "back": {'roll': 0., 'pitch': 0., 'yaw': np.pi},
    "up": {'roll': 0., 'pitch': np.pi / 2, 'yaw': 0.},
    "down": {'roll': 0., 'pitch': -np.pi / 2, 'yaw': 0.},
    "left": {'roll': 0., 'pitch': 0., 'yaw': -np.pi / 2},
    "right": {'roll': 0., 'pitch': 0., 'yaw': np.pi / 2},
}


def z_distance_to_depth(z_distance: np.ndarray, fov_x: float, fov_y: float) -> np.ndarray:
    """Convert optical-axis depth to ray distance; input shape (B, H, W, 1), FOV in degrees."""
    *_, H, W, C = z_distance.shape

    fov_x_rad = np.radians(fov_x)
    fov_y_rad = np.radians(fov_y)

    # Pinhole focal lengths in pixels.
    f_x = W / (2 * np.tan(fov_x_rad / 2))
    f_y = H / (2 * np.tan(fov_y_rad / 2))

    u, v = np.meshgrid(np.arange(W), np.arange(H))

    u_normalized = (u - W / 2) / f_x
    v_normalized = (v - H / 2) / f_y

    # Angle between each pixel ray and the optical axis.
    angles = np.arctan(np.sqrt(u_normalized**2 + v_normalized**2))

    angles = repeat(angles, 'h w -> 1 h w 1')
    angles = np.broadcast_to(angles, z_distance.shape)

    depth_map = z_distance / np.cos(angles)

    return depth_map


def create_feathering_mask(h, w):
    """Create a (1, H, W) weight mask that decreases from the center to the edges."""
    center_x, center_y = w / 2, h / 2
    x_ramp = np.abs(np.arange(w) - center_x) / float(center_x)
    y_ramp = np.abs(np.arange(h) - center_y) / float(center_y)
    ramp = np.maximum(x_ramp[np.newaxis, :], y_ramp[:, np.newaxis])
    mask = 1 - ramp
    mask = np.clip(mask, 0, 1)
    return mask[np.newaxis, :, :]


def project_image_and_mask(
        img_np: np.ndarray,
        rots: dict,
        equi_height: int,
        equi_width: int,
        original_fov: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Project a perspective image and its feathering mask onto an equirectangular grid."""
    pers_h, pers_w, _ = img_np.shape
    # equilib expects channel-first arrays: (C, H, W).
    pers_img_np = np.transpose(img_np, (2, 0, 1))

    equi_img = pers2equi(
        pers=pers_img_np, rots=rots, height=equi_height, width=equi_width,
        fov_x=original_fov, mode="bilinear"
    )

    feather_mask = create_feathering_mask(pers_h, pers_w)
    equi_mask = pers2equi(
        pers=feather_mask * 255, rots=rots, height=equi_height, width=equi_width,
        fov_x=original_fov, mode="bilinear"
    )
    equi_mask /= 255.0
    equi_mask[equi_mask < 0.01] = 0

    return equi_img.astype(np.float32), equi_mask.astype(np.float32)

def process_rgb_frame(
    frame_id: str,
    output_dir: str,
    base_dir: str,
    equi_height: int,
    equi_width: int,
    original_fov: float,
):
    """Blend the six projected views and save the RGB panorama."""
    numerator = np.zeros((3, equi_height, equi_width), dtype=np.float32)
    denominator = np.zeros((1, equi_height, equi_width), dtype=np.float32)

    image_found = False
    for view in VIEWS:
        path = os.path.join(base_dir, f'rgb_{view}_fov{int(original_fov)}', f'{frame_id}.png')
        if not os.path.exists(path):
            continue

        try:
            pers_img = Image.open(path).convert("RGB")
            pers_img_np = np.asarray(pers_img, dtype=np.uint8)
            image_found = True
        except FileNotFoundError:
            continue

        rots = ROTATIONS[view]
        equi_img, equi_mask = project_image_and_mask(pers_img_np, rots, equi_height, equi_width, original_fov)

        numerator += equi_img * equi_mask
        denominator += equi_mask

    if not image_found:
        return

    denominator[denominator == 0] = 1e-6
    merged_equi = numerator / denominator

    merged_equi_pil = np.transpose(merged_equi, (1, 2, 0))
    output_image = Image.fromarray(np.clip(merged_equi_pil, 0, 255).astype('uint8'))
    output_path = os.path.join(output_dir, f"{frame_id}.png")
    output_image.save(output_path)


def visualize_depth(depth_array_meters):
    """Convert metric depth to a logarithmic color visualization."""
    far_plane = 1000.0
    log_depth = np.log(depth_array_meters + 1) / np.log(far_plane + 1)

    # Clip before conversion to uint8 to prevent overflow beyond the far plane.
    log_depth_clipped = np.clip(log_depth, 0.0, 1.0)

    depth_visual = (log_depth_clipped * 255).astype(np.uint8)
    depth_colormap = cv2.applyColorMap(depth_visual, cv2.COLORMAP_JET)
    depth_colormap_rgb = cv2.cvtColor(depth_colormap, cv2.COLOR_BGR2RGB)
    return Image.fromarray(depth_colormap_rgb)

VIEW_TO_FACETYPE = {
    "front": 0,
    "right": 1,
    "back": 2,
    "left": 3,
    "up": 4,
    "down": 5,
}

def process_depth_frame(
    frame_id: str,
    output_dir_npy: str,
    output_dir_visual: str,
    base_dir: str,
    equi_height: int,
    equi_width: int,
    original_fov: float,
):
    """Return a ray-distance panorama assembled from the six projected depth views."""

    stitched_panorama_raw = np.zeros((equi_height, equi_width), dtype=np.float32)

    # 0:front, 1:right, 2:back, 3:left, 4:up, 5:down
    facetype_map = py360convert.utils.equirect_facetype(equi_height, equi_width)

    data_found = False
    for view in VIEWS:
        path = os.path.join(base_dir, f'depth_npy_{view}_fov_{int(original_fov)}', f'{frame_id}.npy')
        if not os.path.exists(path):
            continue

        try:
            depth_array_z  = np.load(path)
            data_found = True
        except FileNotFoundError:
            continue

        # Convert optical-axis depth to ray distance before projection.
        depth_array_z_ch = depth_array_z[np.newaxis, ..., np.newaxis] # (1, H, W, 1)
        pers_distance_np = z_distance_to_depth(depth_array_z_ch, original_fov, original_fov).squeeze()

        pers_distance_np_ch = pers_distance_np[np.newaxis, ...] # (1, H, W)
        rots = ROTATIONS[view]

        equi_dist_temp = pers2equi(
            pers=pers_distance_np_ch,
            rots=rots,
            height=equi_height,
            width=equi_width,
            fov_x=original_fov,
            mode="nearest"
        )

        equi_dist_temp = equi_dist_temp.squeeze()

        # Select one cubemap face per pixel to preserve depth and label boundaries.
        facetype_idx = VIEW_TO_FACETYPE[view]
        mask = (facetype_map == facetype_idx)

        stitched_panorama_raw[mask] = equi_dist_temp[mask]

    if not data_found:
        return None

    return stitched_panorama_raw


def process_segmentation_frame(
    frame_id: str,
    output_dir_seg: str,
    base_dir: str,
    equi_height: int,
    equi_width: int,
    original_fov: float,
):
    """Project semantic class IDs with nearest-neighbor sampling and save the panorama."""

    stitched_panorama_raw = np.zeros((equi_height, equi_width), dtype=np.uint8)

    # 0:front, 1:right, 2:back, 3:left, 4:up, 5:down
    facetype_map = py360convert.utils.equirect_facetype(equi_height, equi_width)

    data_found = False
    for view in VIEWS:
        path = os.path.join(base_dir, f'segmentation_{view}_fov{int(original_fov)}', f'{frame_id}.png')

        if not os.path.exists(path):
            continue

        try:
            seg_img = Image.open(path)
            pers_seg_np = np.array(seg_img)
            data_found = True
        except FileNotFoundError:
            continue

        pers_seg_np_ch = pers_seg_np[np.newaxis, ...] # (1, H, W)

        rots = ROTATIONS[view]

        equi_seg_temp = pers2equi(
            pers=pers_seg_np_ch,
            rots=rots,
            height=equi_height,
            width=equi_width,
            fov_x=original_fov,
            mode="nearest"
        )

        equi_seg_temp = equi_seg_temp.squeeze().astype(np.uint8)

        # Select one cubemap face per pixel to preserve depth and label boundaries.
        facetype_idx = VIEW_TO_FACETYPE[view]
        mask = (facetype_map == facetype_idx)

        stitched_panorama_raw[mask] = equi_seg_temp[mask]

    if not data_found:
        return None

    output_path_seg = os.path.join(output_dir_seg, f"{frame_id}.png")
    os.makedirs(output_dir_seg, exist_ok=True)
    Image.fromarray(stitched_panorama_raw).save(output_path_seg)

    return stitched_panorama_raw


def source_frames(base_dir, fov):
    """Reject incomplete modalities instead of silently stitching black regions."""
    root = Path(base_dir)
    folders = [(root / f'rgb_{view}_fov{fov}', '.png') for view in VIEWS]
    folders += [(root / f'depth_npy_{view}_fov_{fov}', '.npy') for view in VIEWS]
    has_seg = any((root / f'segmentation_{view}_fov{fov}').exists() for view in VIEWS)
    if has_seg:
        folders += [(root / f'segmentation_{view}_fov{fov}', '.png') for view in VIEWS]
    reference = None
    for folder, extension in folders:
        if not folder.is_dir():
            raise ValueError(f'Missing source directory: {folder}')
        frames = {path.stem for path in folder.glob(f'*{extension}')}
        if not frames or not all(frame.isdigit() for frame in frames):
            raise ValueError(f'Expected nonempty numeric frame filenames in {folder}')
        if reference is None:
            reference = frames
        elif frames != reference:
            raise ValueError(f'Frame IDs do not match in {folder}; missing={len(reference - frames)}, extra={len(frames - reference)}')
    return sorted(reference, key=int), has_seg


def process_frame_worker(task):
    frame_id, base_dir, equi_h, equi_w, fov, has_seg = task
    root = Path(base_dir)
    # Validate source shapes before producing any part of this frame.
    expected_shape = None
    for view in VIEWS:
        with Image.open(root / f'rgb_{view}_fov{int(fov)}' / f'{frame_id}.png') as rgb:
            width, height = rgb.size
        if width != height:
            raise ValueError(f'Frame {frame_id}: source images must be square')
        shape = (height, width)
        if expected_shape is not None and shape != expected_shape:
            raise ValueError(f'Frame {frame_id}: camera resolutions differ')
        expected_shape = shape
        depth = np.load(root / f'depth_npy_{view}_fov_{int(fov)}' / f'{frame_id}.npy', allow_pickle=False)
        if depth.shape != shape or not np.isfinite(depth).all() or (depth < 0).any():
            raise ValueError(f'Frame {frame_id}: invalid depth in view {view}')
        if has_seg:
            with Image.open(root / f'segmentation_{view}_fov{int(fov)}' / f'{frame_id}.png') as seg:
                if seg.size != (width, height) or np.asarray(seg).ndim != 2:
                    raise ValueError(f'Frame {frame_id}: invalid labels in view {view}')
    output_rgb = str(root / 'panorama_rgb')
    output_depth = str(root / 'panorama_depth_npy')
    output_visual = str(root / 'panorama_depth_visual')
    output_seg = str(root / 'panorama_segmentation')
    process_rgb_frame(frame_id, output_rgb, base_dir, equi_h, equi_w, fov)
    depth = process_depth_frame(frame_id, output_depth, output_visual, base_dir, equi_h, equi_w, fov)
    if has_seg:
        process_segmentation_frame(frame_id, output_seg, base_dir, equi_h, equi_w, fov)
    np.save(Path(output_depth) / f'{frame_id}.npy', depth)
    visualize_depth(depth).save(Path(output_visual) / f'{frame_id}.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base_dir', required=True)
    parser.add_argument('--num_process', type=int, default=4)
    parser.add_argument('--equi_height', type=int, default=1200)
    parser.add_argument('--equi_width', type=int, default=2400)
    parser.add_argument('--original_fov', type=float, required=True)
    parser.add_argument('--re_stitch', action='store_true')
    args = parser.parse_args()
    if min(args.num_process, args.equi_height, args.equi_width) <= 0:
        parser.error('Process count and image dimensions must be positive')
    if not 90 <= args.original_fov < 180 or not args.original_fov.is_integer():
        parser.error('--original_fov must be an integer in [90, 180)')
    if args.equi_width != 2 * args.equi_height or args.equi_height % 2:
        parser.error('Panoramas must have even height and width = 2 * height')
    root = Path(args.base_dir)
    frame_ids, has_seg = source_frames(root, int(args.original_fov))
    config = dict(equi_height=args.equi_height, equi_width=args.equi_width,
                  original_fov=args.original_fov, segmentation=has_seg)
    config_path = root / 'stitch_config.json'
    if config_path.exists() and not args.re_stitch:
        if json.loads(config_path.read_text()) != config:
            parser.error('Stitch settings changed; use --re_stitch')
    outputs = [('panorama_rgb', '.png'), ('panorama_depth_npy', '.npy'),
               ('panorama_depth_visual', '.png')]
    if has_seg:
        outputs.append(('panorama_segmentation', '.png'))
    # A directory without metadata may contain products from different settings.
    can_resume = config_path.exists() and not args.re_stitch
    for folder, suffix in outputs:
        (root / folder).mkdir(exist_ok=True)
        if args.re_stitch:
            for old_file in (root / folder).glob(f'*{suffix}'):
                old_file.unlink()
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    pending = [frame for frame in frame_ids if not can_resume or not all(
        (root / folder / f'{frame}{suffix}').is_file() for folder, suffix in outputs)]
    print(f'{len(frame_ids)} source frames; {len(pending)} frames to stitch')
    tasks = [(frame, str(root), args.equi_height, args.equi_width, args.original_fov, has_seg)
             for frame in pending]
    if tasks:
        with multiprocessing.Pool(processes=args.num_process) as pool:
            for _ in tqdm(pool.imap_unordered(process_frame_worker, tasks), total=len(tasks)):
                pass
    print('Stitching complete.')


if __name__ == '__main__':
    main()
