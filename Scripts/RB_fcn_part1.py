#%% functions RapidBenthos
# ==============================================================================
# RapidBenthos — RB_fcn_part1.py
# Author  : Mohamed Bouchalkha — CREOCEAN
# Date    : 2026
# Fix     : Replaced tqdm in camera_point_from_segment_centerPoint with manual
#           progress printing to eliminate the tqdm monitor thread that caused
#           "Fatal Python error: none_dealloc" when running alongside Metashape
#           C++ extension objects (refcount conflict in Python 3.10)
# ==============================================================================

import os.path
import os
import sys

from datetime import datetime

try:
    import Metashape
except ImportError:
    Metashape = None

import pandas as pd
import numpy as np
import multiprocess as mp
import math
from scipy.spatial.distance import cdist
from math import sqrt
import rasterio

import geopandas as gpd
from shapely.geometry import Polygon
from functools import reduce
from tqdm import tqdm
from time import time


#%% RB_FilterSHP_clean
def Filter_segments(Segment_gpkg, output_segments_shp_path, output_pts_shp_path, output_pts_csv_path):
    segments_df = gpd.read_file(Segment_gpkg)
    segments_df['area'] = segments_df.area
    segments_df_treshold_big = segments_df[(segments_df['area'] >= 0.075) & (segments_df['area'] < 2.5)]
    segment_df_treshold_small = segments_df[(segments_df['area'] >= 0.00005) & (segments_df['area'] < 0.075)]

    segment_small_filled = segment_df_treshold_small
    sizelim = 0.05

    for ind, row in tqdm(segment_small_filled.iterrows(), total=segment_small_filled.shape[0]):
        rings = [i for i in row["geometry"].interiors]
        if len(rings) > 0:
            newgeom = None
            to_fill = [Polygon(ring) for ring in rings if Polygon(ring).area < sizelim]
            if len(to_fill) > 0:
                newgeom = reduce(lambda geom1, geom2: geom1.union(geom2), [row["geometry"]] + to_fill)
                segment_small_filled.loc[[ind], 'geometry'] = newgeom

    geoms = segment_small_filled.geometry.unary_union
    segment_df_small_filled = gpd.GeoDataFrame(geometry=[geoms])
    segment_df_small_filled = segment_df_small_filled.explode().reset_index(drop=True)

    segment_df_all = pd.concat([segment_df_small_filled, segments_df_treshold_big])
    segment_df_all = segment_df_all.reset_index(drop=True)

    segment_df_all['area'] = segment_df_all.area
    segment_df_all["length"] = segment_df_all.length
    segment_df_all["pp"] = segment_df_all.apply(
        lambda x: ((x["area"] * (4 * (math.pi))) / (x["length"] ** 2)), axis=1)
    segment_df_all = segment_df_all[
        (segment_df_all["area"] >= 0.005) |
        ((segment_df_all["area"].between(0.0025, 0.005, inclusive="neither")) & (segment_df_all['pp'] >= 0.25)) |
        ((segment_df_all["area"].between(0.0005, 0.0025)) & (segment_df_all['pp'] >= 0.3))
    ]

    segment_df_all['segment_un'] = segment_df_all.index
    segments_df_filtered = segment_df_all.drop(columns=['value'])

    segments_df_filtered = gpd.GeoDataFrame(segments_df_filtered, geometry='geometry')
    segments_df_filtered['center_point'] = segments_df_filtered.representative_point()
    segments_df_filtered['area'] = segments_df_filtered.area
    segments_df_filtered['center_point_x'] = segments_df_filtered.center_point.apply(lambda p: p.x)
    segments_df_filtered['center_point_y'] = segments_df_filtered.center_point.apply(lambda p: p.y)
    segments_df_filtered['average_z'] = -5
    segments_pts_df = segments_df_filtered.drop(['geometry'], axis=1)
    segments_df_filtered = segments_df_filtered.drop(['center_point'], axis=1)
    segments_pts_df = gpd.GeoDataFrame(segments_pts_df, geometry='center_point')
    segments_df_filtered.to_file(output_segments_shp_path)
    segments_pts_df.to_file(output_pts_shp_path)
    segments_pts_df.to_csv(output_pts_csv_path)

    return segments_df_filtered, segments_pts_df


#%% Import functions for point_from_RB_centroid_no_filter
def convert_time(seconds):
    mins, sec = divmod(seconds, 60)
    hour, mins = divmod(mins, 60)
    if hour > 0:
        return "{:.0f} hour, {:.0f} minutes".format(hour, mins)
    elif mins > 5:
        return "{:.0f} minutes".format(mins)
    elif mins >= 2:
        return "{:.0f} minutes, {:.0f} seconds".format(mins, sec)
    elif mins > 0:
        return "{:.0f} minute, {:.0f} seconds".format(mins, sec)
    else:
        return "{:.2f} seconds".format(sec)


def timestamp():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


class Point3D:
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def distance(self, p2):
        return sqrt((self.x - p2.x) ** 2 + (self.y - p2.y) ** 2 + (self.z - p2.z) ** 2)

    def distance_2D(self, other):
        return sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


#%% Import rotation functions
class CameraStats():
    def __init__(self, camera):
        chunk = camera.chunk

        self.camera = camera
        self.estimated_location = None
        self.estimated_rotation = None
        self.reference_location = None
        self.reference_rotation = None
        self.error_location = None
        self.error_rotation = None
        self.sigma_location = None
        self.sigma_rotation = None

        if not camera.transform:
            return

        transform = chunk.transform.matrix
        crs = chunk.crs

        if chunk.camera_crs:
            transform = Metashape.CoordinateSystem.datumTransform(crs, chunk.camera_crs) * transform
            crs = chunk.camera_crs

        ecef_crs = self.getCartesianCrs(crs)

        camera_transform = transform * camera.transform
        antenna_transform = self.getAntennaTransform(camera.sensor)
        location_ecef = camera_transform.translation() + camera_transform.rotation() * antenna_transform.translation()
        rotation_ecef = camera_transform.rotation() * antenna_transform.rotation()

        self.estimated_location = Metashape.CoordinateSystem.transform(location_ecef, ecef_crs, crs)
        if camera.reference.location:
            self.reference_location = camera.reference.location
            self.error_location = (
                Metashape.CoordinateSystem.transform(self.estimated_location, crs, ecef_crs) -
                Metashape.CoordinateSystem.transform(self.reference_location, crs, ecef_crs)
            )
            self.error_location = crs.localframe(location_ecef).rotation() * self.error_location

        if (chunk.euler_angles == Metashape.EulerAnglesOPK or
                chunk.euler_angles == Metashape.EulerAnglesPOK):
            localframe = crs.localframe(location_ecef)
        else:
            localframe = ecef_crs.localframe(location_ecef)

        self.estimated_rotation = Metashape.utils.mat2euler(
            localframe.rotation() * rotation_ecef, chunk.euler_angles)
        if camera.reference.rotation:
            self.reference_rotation = camera.reference.rotation
            self.error_rotation = self.estimated_rotation - self.reference_rotation
            self.error_rotation.x = (self.error_rotation.x + 180) % 360 - 180
            self.error_rotation.y = (self.error_rotation.y + 180) % 360 - 180
            self.error_rotation.z = (self.error_rotation.z + 180) % 360 - 180

        if camera.location_covariance:
            T = crs.localframe(location_ecef) * transform
            R = T.rotation() * T.scale()
            cov = R * camera.location_covariance * R.t()
            self.sigma_location = Metashape.Vector([
                math.sqrt(cov[0, 0]), math.sqrt(cov[1, 1]), math.sqrt(cov[2, 2])])

        if camera.rotation_covariance:
            T = localframe * camera_transform
            R0 = T.rotation()
            dR = antenna_transform.rotation()
            da = Metashape.utils.dmat2euler(R0 * dR, R0 * self.makeRotationDx(0) * dR, chunk.euler_angles)
            db = Metashape.utils.dmat2euler(R0 * dR, R0 * self.makeRotationDy(0) * dR, chunk.euler_angles)
            dc = Metashape.utils.dmat2euler(R0 * dR, R0 * self.makeRotationDz(0) * dR, chunk.euler_angles)
            R = Metashape.Matrix([
                [da.x, db.x, dc.x],
                [da.y, db.y, dc.y],
                [da.z, db.z, dc.z]
            ])
            self.sigma_rotation = Metashape.Vector([
                math.sqrt(abs(camera.rotation_covariance[0, 0])),
                math.sqrt(abs(camera.rotation_covariance[1, 1])),
                math.sqrt(abs(camera.rotation_covariance[2, 2]))
            ])

    def getCartesianCrs(self, crs):
        ecef_crs = Metashape.CoordinateSystem()
        ecef_crs.init("LOCAL_CS[\"Local Coordinates (m)\","
                       "LOCAL_DATUM[\"Local Datum\",0],"
                       "UNIT[\"metre\",1,AUTHORITY[\"EPSG\",\"9001\"]]]")
        return ecef_crs

    def getAntennaTransform(self, sensor):
        location = sensor.antenna.location
        if location is None:
            location = sensor.antenna.location_ref
        rotation = sensor.antenna.rotation
        if rotation is None:
            rotation = sensor.antenna.rotation_ref
        return Metashape.Matrix.Translation(location) * Metashape.Matrix.Rotation(
            Metashape.utils.euler2mat(rotation, Metashape.EulerAnglesYPR))

    def makeRotationDx(self, alpha):
        return Metashape.Matrix([
            [0, 0, 0],
            [0, -math.sin(alpha), -math.cos(alpha)],
            [0, math.cos(alpha), -math.sin(alpha)]
        ])

    def makeRotationDy(self, alpha):
        return Metashape.Matrix([
            [-math.sin(alpha), 0, math.cos(alpha)],
            [0, 0, 0],
            [-math.cos(alpha), 0, -math.sin(alpha)]
        ])

    def makeRotationDz(self, alpha):
        return Metashape.Matrix([
            [-math.sin(alpha), -math.cos(alpha), 0],
            [math.cos(alpha), -math.sin(alpha), 0],
            [0, 0, 0]
        ])

    def getEulerAnglesName(self, euler_angles):
        if euler_angles == Metashape.EulerAnglesOPK:
            return "OPK"
        elif euler_angles == Metashape.EulerAnglesPOK:
            return "POK"
        elif euler_angles == Metashape.EulerAnglesYPR:
            return "YPR"
        else:
            return "Unknown"

    def printVector(self, f, name, value, precision):
        f.write(("\t{:s}: " + "{:." + str(precision) + "f} ").format(
            name, value.x, value.y, value.z))

    def write(self, f):
        euler_name = self.getEulerAnglesName(self.camera.chunk.euler_angles)
        f.write(self.camera.label + "\n")
        if self.reference_location:
            self.printVector(f, "  XYZ source", self.reference_location, 6)
        if self.error_location:
            self.printVector(f, "  XYZ error", self.error_location, 6)
        if self.estimated_location:
            self.printVector(f, "  XYZ estimated", self.estimated_location, 6)
        if self.sigma_location:
            self.printVector(f, "  XYZ sigma", self.sigma_location, 6)
        if self.reference_rotation:
            self.printVector(f, "  " + euler_name + " source", self.reference_rotation, 3)
        if self.error_rotation:
            self.printVector(f, "  " + euler_name + " error", self.error_rotation, 3)
        if self.estimated_rotation:
            self.printVector(f, "  " + euler_name + " estimated", self.estimated_rotation, 3)
        if self.sigma_rotation:
            self.printVector(f, "  " + euler_name + " sigma", self.sigma_rotation, 3)


#%% point_from_RB_centroid_no_filter
def camera_point_from_segment_centerPoint(MetashapeProject_path, Chunk_number, PhotoPath, OutputPath, CenterPoint_path):
    # --------------------------------------------------------------------------
    # CRITICAL FIX : disable tqdm monitor thread BEFORE any Metashape API call
    # The tqdm monitor thread causes "Fatal Python error: none_dealloc" when
    # Metashape iterates over C++ camera objects in Python 3.10.
    # Root cause : tqdm monitor thread holds a reference to Python internals
    # that conflict with Metashape's C extension refcounting.
    # Solution   : set monitor_interval=0 to prevent thread creation entirely,
    #              AND replace tqdm in the centroid loop with manual print()
    #              so NO tqdm thread is alive during Metashape iteration.
    # --------------------------------------------------------------------------
    import tqdm as _tqdm_module
    _tqdm_module.tqdm.monitor_interval = 0

    # ── OUVERTURE PROJET ──────────────────────────────────────
    doc = Metashape.Document()
    doc.open(MetashapeProject_path)

    ts = timestamp()
    save_path = OutputPath.format(ts)

    Empty_centroid = []

    chunk = doc.chunks[Chunk_number]
    T     = chunk.transform.matrix
    crs   = chunk.crs

    # ── CHARGER CSV ───────────────────────────────────────────
    RB_centroid = pd.read_csv(CenterPoint_path)

    print(f"Centroides charges : {len(RB_centroid)}")
    print(f"  X UTM : {RB_centroid.center_point_x.min():.1f} -> {RB_centroid.center_point_x.max():.1f}")
    print(f"  Y UTM : {RB_centroid.center_point_y.min():.1f} -> {RB_centroid.center_point_y.max():.1f}")

    # ── FIX CRS : UTM 32737 → CRS du chunk (WGS84) ───────────
    print("\nConversion UTM 32737 -> CRS chunk ...")
    utm_crs = Metashape.CoordinateSystem("EPSG::32737")

    cx_wgs, cy_wgs = [], []
    for _, row in RB_centroid.iterrows():
        pt_utm = Metashape.Vector((row.center_point_x, row.center_point_y, row.average_z))
        pt_wgs = Metashape.CoordinateSystem.transform(pt_utm, utm_crs, crs)
        cx_wgs.append(pt_wgs.x)
        cy_wgs.append(pt_wgs.y)

    RB_centroid["cx_wgs"] = cx_wgs
    RB_centroid["cy_wgs"] = cy_wgs
    print(f"  X WGS84 : {RB_centroid.cx_wgs.min():.6f} -> {RB_centroid.cx_wgs.max():.6f}")
    print(f"  Y WGS84 : {RB_centroid.cy_wgs.min():.6f} -> {RB_centroid.cy_wgs.max():.6f}")
    print("Conversion terminee")

    # ── CHARGER MODELE 3D ─────────────────────────────────────
    print("\nLoading model ...")
    tic = time()
    model   = chunk.models[0]
    v_Trans = []
    for V in model.vertices:
        transform_vertices = chunk.crs.project(T.mulp(V.coord))
        v_Trans.append(transform_vertices)
    v_Trans = np.asarray(v_Trans)
    print(f"Done in {convert_time(time() - tic)}")
    print(f"  X modele : {v_Trans[:, 0].min():.6f} -> {v_Trans[:, 0].max():.6f}")
    print(f"  Y modele : {v_Trans[:, 1].min():.6f} -> {v_Trans[:, 1].max():.6f}")

    # ── CAMERAS ───────────────────────────────────────────────
    c, cams, c_trans = [], [], []
    for cam in chunk.cameras:
        try:
            transform_vertices = chunk.crs.project(T.mulp(cam.center))
            c_trans.append(transform_vertices)
            cams.append(cam)
            c.append(cam.center)
        except:
            continue
    c       = np.asarray(c)
    cams    = np.asarray(cams)
    c_trans = np.asarray(c_trans)

    # ── EXTRACTION UV ─────────────────────────────────────────
    out_df_list  = []
    total        = RB_centroid.shape[0]
    report_step  = max(1, total // 20)   # affiche la progression tous les 5%

    # CRITICAL : boucle principale SANS tqdm
    # tqdm wrapping iterrows() cree un monitor thread qui crashe avec Metashape
    # Remplacement par print() manuel — comportement identique, zero thread
    for idx, (index, row) in enumerate(RB_centroid.iterrows()):

        # Progression manuelle tous les 5% (remplace tqdm)
        if idx % report_step == 0 or idx == total - 1:
            pct = (idx + 1) / total * 100
            print(f"  Progression : {idx + 1}/{total} ({pct:.0f}%)", flush=True)

        samID = row.segment_un
        cx    = row.cx_wgs
        cy    = row.cy_wgs

        verts = []

        # eps progressif en degres (WGS84)
        # 0.0001 deg ~ 11m | 0.0005 ~ 55m | 0.001 ~ 110m | 0.002 ~ 220m
        for eps in [0.0001, 0.0005, 0.001, 0.002]:
            x_cond = np.where((v_Trans[:, 0] > cx - eps) & (v_Trans[:, 0] < cx + eps))
            y_cond = np.where((v_Trans[:, 1] > cy - eps) & (v_Trans[:, 1] < cy + eps))
            verts  = v_Trans[np.intersect1d(x_cond, y_cond)]
            if len(verts) > 0:
                break

        if len(verts) == 0:
            Empty_centroid.append(samID)
            continue

        xy_max_z = list(max(verts, key=lambda x: x[2])[:])
        X, Y, Z  = xy_max_z
        p = T.inv().mulp(crs.unproject(Metashape.Vector((X, Y, Z))))

        cam_UV = []
        for camera in chunk.cameras:
            try:
                if not camera.project(p):
                    continue
                u = camera.project(p).x
                v = camera.project(p).y
                if (u < 0 or u > camera.sensor.width or
                        v < 0 or v > camera.sensor.height):
                    continue
                estimated_coord = crs.project(T.mulp(camera.center))
                cam_vec_int = camera.transform.mulv(Metashape.Vector([0, 0, 1]))
                cam_vec_ext = chunk.transform.matrix.mulv(cam_vec_int)
                cam_vec_ext.normalize()

                s1 = Point3D(X, Y, Z)
                s2 = Point3D(estimated_coord.x, estimated_coord.y, estimated_coord.z)

                cam_UV.append({
                    'camera_id'               : camera.label,
                    'U'                       : u,
                    'V'                       : v,
                    'dis_3D'                  : s1.distance(s2),
                    'dis_2D'                  : s1.distance_2D(s2),
                    'camera_path'             : camera.photo.path,
                    'camera_rotation'         : CameraStats(camera).estimated_rotation,
                    'SAM_ID'                  : samID,
                    'cam_enable'              : camera.enabled,
                    'camera_center_coordinate': s2,
                })
            except:
                continue

        if len(cam_UV) == 0:
            continue

        uv_cam_df = pd.DataFrame(cam_UV)
        uv_bbox   = uv_cam_df[
            (uv_cam_df["U"] > 750)  & (uv_cam_df["U"] < 7506) &
            (uv_cam_df["V"] > 750)  & (uv_cam_df["V"] < 4754)
        ]
        uv_10 = uv_bbox.sort_values(by=['dis_2D', 'dis_3D']).head(10)

        for _, r in uv_10.iterrows():
            out_df_list.append({
                'SAM_centroid'           : samID,
                'camera_id'              : r.camera_id + '.JPG',
                'camera_path'            : r.camera_path,
                'U'                      : r.U,
                'V'                      : r.V,
                'point_x'               : row.center_point_x,
                'point_y'               : row.center_point_y,
                'vertex_x'              : X,
                'vertex_y'              : Y,
                'vertex_z'              : Z,
                'cam_estimated_x'       : r.camera_center_coordinate.x,
                'cam_estimated_y'       : r.camera_center_coordinate.y,
                'cam_estimated_z'       : r.camera_center_coordinate.z,
                'distance_3D_cam_vert'  : r.dis_3D,
                'distance_2D_cam_vert'  : r.dis_2D,
                'camera_rotation'       : r.camera_rotation,
                'camera_yaw'            : r.camera_rotation[0],
                'camera_pitch'          : r.camera_rotation[1],
                'camera_roll'           : r.camera_rotation[2],
                'camera_enable'         : r.cam_enable,
            })

    # ── SAVE ──────────────────────────────────────────────────
    camera_UV_csv = pd.DataFrame(out_df_list)

    print(f"\n{'='*50}")
    print(f"Points UV trouves      : {len(out_df_list)}")
    print(f"Centroides sans vertex : {len(Empty_centroid)} / {len(RB_centroid)}")

    if len(camera_UV_csv) > 0:
        if not os.path.exists(save_path):
            camera_UV_csv.to_csv(save_path, index=False)
        else:
            camera_UV_csv.to_csv(save_path, mode='a', index=False, header=False)
        print(f"Fichier sauvegarde : {save_path}")
        print(f"Cameras uniques    : {camera_UV_csv.camera_id.nunique()}")
        print(f"Segments uniques   : {camera_UV_csv.SAM_centroid.nunique()}")
    else:
        print("Aucun point trouve — verifier le CRS du chunk dans Metashape")

    return camera_UV_csv


def create_hexagon(l, x, y):
    c = [[x + math.cos(math.radians(angle)) * l,
          y + math.sin(math.radians(angle)) * l]
         for angle in range(0, 360, 60)]
    return Polygon(c)


def create_hexgrid(bbox, side):
    grid   = []
    v_step = math.sqrt(3) * side
    h_step = 1.5 * side

    x_min = min(bbox[0], bbox[2])
    x_max = max(bbox[0], bbox[2])
    y_min = min(bbox[1], bbox[3])
    y_max = max(bbox[1], bbox[3])

    h_skip = math.ceil(x_min / h_step) - 1
    h_start = h_skip * h_step

    v_skip = math.ceil(y_min / v_step) - 1
    v_start = v_skip * v_step

    h_end = x_max + h_step
    v_end = y_max + v_step

    if v_start - (v_step / 2.0) < y_min:
        v_start_array = [v_start + (v_step / 2.0), v_start]
    else:
        v_start_array = [v_start - (v_step / 2.0), v_start]

    v_start_idx = int(abs(h_skip) % 2)
    c_x = h_start
    c_y = v_start_array[v_start_idx]
    v_start_idx = (v_start_idx + 1) % 2

    while c_x < h_end:
        while c_y < v_end:
            grid.append((c_x, c_y))
            c_y += v_step
        c_x += h_step
        c_y = v_start_array[v_start_idx]
        v_start_idx = (v_start_idx + 1) % 2

    return grid


def filter_segments_by_area(shapefile, max, min):
    shapefile['area'] = shapefile['geometry'].area.round(4)
    shapefile_min = shapefile[shapefile['area'] >= min]
    SAM_Range = shapefile_min[shapefile_min['area'] <= max]
    return SAM_Range


def hexagrid(ortho, resolution, full_grid_path, segments_df_filtered,
             clip_grid_path, hexagrid_SAM_union_path_seg_shp,
             hexagrid_SAM_union_pst_shp, hexagrid_SAM_union_path_pts_csv):

    dataset = rasterio.open(ortho)
    Res     = resolution
    edge    = math.sqrt(Res ** 2 / (3 / 2 * math.sqrt(3)))
    hex_centers = create_hexgrid(dataset.bounds, edge)
    hexa    = ([create_hexagon(edge, center[0], center[1]) for center in hex_centers])

    p       = gpd.GeoSeries(hexa)
    hexagrid_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(p))
    hexagrid_gdf.to_file(full_grid_path)

    segments = gpd.read_file(segments_df_filtered)
    hexagrid_segments_df_filtered_difference = hexagrid_gdf.overlay(segments, how='difference')
    hexagrid_segments_df_filtered_difference['segment_un'] = hexagrid_segments_df_filtered_difference.index
    hexagrid_segments_df_filtered_difference['segment_un'] = (
        'Hexa_' + hexagrid_segments_df_filtered_difference['segment_un'].astype(str))
    hexagrid_segments_df_filtered_difference['area'] = hexagrid_segments_df_filtered_difference.area
    hexagrid_segments_df_filtered_difference.to_file(clip_grid_path)

    segments2    = segments[['geometry', 'segment_un', 'area']]
    hexagrid_SAM = gpd.GeoDataFrame(pd.concat([segments2, hexagrid_segments_df_filtered_difference]))

    RB_shp_df = gpd.GeoDataFrame(hexagrid_SAM, geometry='geometry')
    RB_shp_df = RB_shp_df[RB_shp_df['area'] > 0]
    RB_shp_df['center_point']   = RB_shp_df.representative_point()
    RB_shp_df['area']            = RB_shp_df.area
    RB_shp_df['center_point_x'] = RB_shp_df.center_point.apply(lambda p: p.x)
    RB_shp_df['center_point_y'] = RB_shp_df.center_point.apply(lambda p: p.y)
    RB_shp_df['average_z']      = -5

    RB_pts_df = RB_shp_df.drop(['geometry'], axis=1)
    RB_pts_df = gpd.GeoDataFrame(RB_pts_df, geometry='center_point')

    RB_pts_df.to_file(hexagrid_SAM_union_pst_shp)
    RB_pts_df.to_csv(hexagrid_SAM_union_path_pts_csv)

    RB_shp_df = RB_shp_df.drop(['center_point'], axis=1)
    RB_shp_df.to_file(hexagrid_SAM_union_path_seg_shp)

    return RB_shp_df, RB_pts_df