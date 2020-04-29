import glob
import os
import sys
import time

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla

import argparse
import logging
import random

from .point_cloud_synthesizer import PointCloudSynthesizer


def main():
    argparser = argparse.ArgumentParser(
        description=__doc__)
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    args = argparser.parse_args()

    logging.basicConfig(
        format='%(levelname)s: %(message)s', level=logging.INFO)

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    try:

        world = client.get_world()
        ego_vehicle = None
        ego_cam = None
        ego_depth = None
        ego_sem = None
        ego_col = None
        ego_lane = None
        ego_obs = None
        ego_gnss = None
        ego_imu = None

        # --------------
        # Start recording
        # --------------
        """
        client.start_recorder('~/tutorial/recorder/recording01.log')
        """

        # --------------
        # Spawn ego vehicle
        # --------------
        ego_bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'ego')
        print('\nEgo role_name is set')
        ego_color = random.choice(
            ego_bp.get_attribute('color').recommended_values)
        ego_bp.set_attribute('color', ego_color)
        print('\nEgo color is set')

        spawn_points = world.get_map().get_spawn_points()
        number_of_spawn_points = len(spawn_points)

        if 0 < number_of_spawn_points:
            random.shuffle(spawn_points)
            ego_transform = spawn_points[0]
            ego_vehicle = world.spawn_actor(ego_bp, ego_transform)
            print('\nEgo is spawned')
        else:
            logging.warning('Could not found any spawn points')

        # --------------
        # Add a RGB camera sensor to ego vehicle.
        # --------------
        cam_bp = None
        cam_bp = world.get_blueprint_library().find('sensor.camera.rgb')
        cam_bp.set_attribute("image_size_x", str(1920))
        cam_bp.set_attribute("image_size_y", str(1080))
        cam_bp.set_attribute("fov", str(105))
        cam_location = carla.Location(2, 0, 1)
        cam_rotation = carla.Rotation(-10, 180, 0)
        cam_transform = carla.Transform(cam_location, cam_rotation)
        ego_cam = world.spawn_actor(
            cam_bp, cam_transform, attach_to=ego_vehicle,
            attachment_type=carla.AttachmentType.SpringArm)
        ego_cam.listen(lambda image: image.save_to_disk(
            'tutorial_pt_cloud/output/%.6d.png' % image.frame))

        # Create the object to fuse depth and segmentation data
        pc_synth = PointCloudSynthesizer(cam_transform)

        # --------------
        # Add a depth camera sensor to ego vehicle.
        # --------------
        depth_bp = None
        depth_bp = world.get_blueprint_library().find('sensor.camera.depth')
        depth_bp.set_attribute("image_size_x", str(1920))
        depth_bp.set_attribute("image_size_y", str(1080))
        depth_bp.set_attribute("fov", str(105))
        depth_location = carla.Location(2, 0, 1)
        depth_rotation = carla.Rotation(-10, 180, 0)
        depth_transform = carla.Transform(depth_location, depth_rotation)
        ego_depth = world.spawn_actor(
            depth_bp, depth_transform, attach_to=ego_vehicle,
            attachment_type=carla.AttachmentType.SpringArm)
        ego_depth.listen(pc_synth.depth_callback)

        # --------------
        # Add a new semantic segmentation camera to my ego
        # --------------
        sem_cam = None
        sem_bp = world.get_blueprint_library().find(
            'sensor.camera.semantic_segmentation')
        sem_bp.set_attribute("image_size_x", str(1920))
        sem_bp.set_attribute("image_size_y", str(1080))
        sem_bp.set_attribute("fov", str(105))
        sem_location = carla.Location(2, 0, 1)
        sem_rotation = carla.Rotation(-10, 180, 0)
        sem_transform = carla.Transform(sem_location, sem_rotation)
        sem_cam = world.spawn_actor(
            sem_bp, sem_transform, attach_to=ego_vehicle,
            attachment_type=carla.AttachmentType.SpringArm)
        # This time, a color converter is applied to the image,
        # to get the semantic segmentation view
        sem_cam.listen(pc_synth.semantic_callback)

        # --------------
        # Enable autopilot for ego vehicle
        # --------------
        ego_vehicle.set_autopilot(True)

        # --------------
        # Game loop. Prevents the script from finishing.
        # --------------
        while True:
            world_snapshot = world.wait_for_tick()

    finally:
        # --------------
        # Stop recording and destroy actors
        # --------------
        client.stop_recorder()
        if ego_vehicle is not None:
            if ego_cam is not None:
                ego_cam.stop()
                ego_cam.destroy()
            if ego_col is not None:
                ego_col.stop()
                ego_col.destroy()
            if ego_lane is not None:
                ego_lane.stop()
                ego_lane.destroy()
            if ego_obs is not None:
                ego_obs.stop()
                ego_obs.destroy()
            if ego_gnss is not None:
                ego_gnss.stop()
                ego_gnss.destroy()
            if ego_imu is not None:
                ego_imu.stop()
                ego_imu.destroy()
            if ego_sem is not None:
                ego_sem.stop()
                ego_sem.destroy()
            if ego_depth is not None:
                ego_depth.stop()
                ego_depth.destroy()
            ego_vehicle.destroy()


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        print('\nDone with tutorial_ego.')
