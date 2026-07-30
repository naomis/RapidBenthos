#%% functions RapidBenthos

import os.path
import os
import sys


from datetime import datetime
import Metashape
import pandas as pd
import numpy as np
from tqdm import tqdm
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
    segments_df['area'] = segments_df.area                                                          #add area
    segments_df_treshold_big = segments_df[(segments_df['area'] >= 0.075) & (segments_df['area'] < 2.5)]      #filter larger shapes
    segment_df_treshold_small = segments_df[(segments_df['area'] >= 0.00005) & (segments_df['area'] < 0.075)]        #filter small shapes

    #fill holes
    segment_small_filled = segment_df_treshold_small
    sizelim = 0.05

    for ind, row in tqdm(segment_small_filled.iterrows(), total= segment_small_filled.shape[0]):
        rings = [i for i in row["geometry"].interiors]                                               #List all interior rings
        if len(rings)>0:                                                                             #If there are any rings
            newgeom=None
            to_fill = [Polygon(ring) for ring in rings if Polygon(ring).area<sizelim]               #List the ones to fill
            if len(to_fill)>0:                                                                      #If there are any to fill
                newgeom = reduce(lambda geom1, geom2: geom1.union(geom2),[row["geometry"]]+to_fill)
                segment_small_filled.loc[[ind], 'geometry'] = newgeom

    #Polygons unary_union
    geoms = segment_small_filled.geometry.unary_union
    segment_df_small_filled = gpd.GeoDataFrame(geometry=[geoms])
    segment_df_small_filled = segment_df_small_filled.explode().reset_index(drop=True)

    #concatinate segments
    segment_df_all = pd.concat([segment_df_small_filled, segments_df_treshold_big])
    segment_df_all = segment_df_all.reset_index(drop=True)

    #calculate area
    segment_df_all['area'] = segment_df_all.area

    #apply plobsy-popper test (pp)
    segment_df_all["length"] = segment_df_all.length
    segment_df_all["pp"] = segment_df_all.apply(lambda x: ((x["area"] * (4*(math.pi))) / (x["length"]**2)) , axis=1)
    segment_df_all = segment_df_all[(segment_df_all["area"] >= 0.005) | ((segment_df_all["area"].between(0.0025, 0.005, inclusive="neither")) & (segment_df_all['pp'] >= 0.25))| ((segment_df_all["area"].between(0.0005, 0.0025)) & (segment_df_all['pp'] >= 0.3))]


    #add unique segemnt ID column and drop Value
    segment_df_all['segment_un']= segment_df_all.index
    segments_df_filtered = segment_df_all.drop(columns = ['value'])

    #create and save polygon and point shp
    segments_df_filtered = gpd.GeoDataFrame(segments_df_filtered, geometry='geometry')
    segments_df_filtered['center_point'] = segments_df_filtered.representative_point()
    segments_df_filtered['area'] = segments_df_filtered.area
    segments_df_filtered['center_point_x'] = segments_df_filtered.center_point.apply(lambda p :p.x)
    segments_df_filtered['center_point_y'] = segments_df_filtered.center_point.apply(lambda p :p.y)
    segments_df_filtered['average_z'] = -5
    segments_pts_df = segments_df_filtered.drop(['geometry'], axis=1)
    segments_df_filtered = segments_df_filtered.drop(['center_point'], axis=1)
    segments_pts_df = gpd.GeoDataFrame(segments_pts_df, geometry='center_point')
    segments_df_filtered.to_file(output_segments_shp_path)
    segments_pts_df.to_file(output_pts_shp_path)
    segments_pts_df.to_csv(output_pts_csv_path)

    return segments_df_filtered, segments_pts_df


#%%Import functions for point_from_RB_centorid_no_filter
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

    def distance_2D(self,other):
        return sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

#%%Import rotation functions

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
            self.error_location = Metashape.CoordinateSystem.transform(self.estimated_location, crs, ecef_crs) - Metashape.CoordinateSystem.transform(self.reference_location, crs, ecef_crs)
            self.error_location = crs.localframe(location_ecef).rotation() * self.error_location

        if chunk.euler_angles == Metashape.EulerAnglesOPK or chunk.euler_angles == Metashape.EulerAnglesPOK:
            localframe = crs.localframe(location_ecef)
        else:
            localframe = ecef_crs.localframe(location_ecef)

        self.estimated_rotation = Metashape.utils.mat2euler(localframe.rotation() * rotation_ecef, chunk.euler_angles)
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
            self.sigma_location = Metashape.Vector([math.sqrt(cov[0, 0]), math.sqrt(cov[1, 1]), math.sqrt(cov[2, 2])])

        if camera.rotation_covariance:
            T = localframe * camera_transform  # to reflect rotation angles ypr (ecef_crs.localfram) or opk (crs.localframe)
            R0 = T.rotation()

            dR = antenna_transform.rotation()

            da = Metashape.utils.dmat2euler(R0 * dR, R0 * self.makeRotationDx(0) * dR, chunk.euler_angles);
            db = Metashape.utils.dmat2euler(R0 * dR, R0 * self.makeRotationDy(0) * dR, chunk.euler_angles);
            dc = Metashape.utils.dmat2euler(R0 * dR, R0 * self.makeRotationDz(0) * dR, chunk.euler_angles);

            R = Metashape.Matrix([da, db, dc]).t()

            cov = R * camera.rotation_covariance * R.t()

            self.sigma_rotation = Metashape.Vector([math.sqrt(cov[0, 0]), math.sqrt(cov[1, 1]), math.sqrt(cov[2, 2])])

    def getCartesianCrs(self, crs):
        ecef_crs = crs.geoccs
        if ecef_crs is None:
            ecef_crs = Metashape.CoordinateSystem('LOCAL')
        return ecef_crs

    def getAntennaTransform(self, sensor):
        location = sensor.antenna.location
        if location is None:
            location = sensor.antenna.location_ref
        if location is None:
            location = Metashape.Vector([0.0, 0.0, 0.0])
        rotation = sensor.antenna.rotation
        if rotation is None:
            rotation = sensor.antenna.rotation_ref
        if rotation is None:
            rotation = Metashape.Vector([0.0, 0.0, 0.0])
        return Metashape.Matrix.Diag((1, -1, -1, 1)) * Metashape.Matrix.Translation(location) * Metashape.Matrix.Rotation(Metashape.Utils.ypr2mat(rotation))

    def makeRotationDx(self, alpha):
        sina = math.sin(alpha)
        cosa = math.cos(alpha)
        return Metashape.Matrix([[0, 0, 0], [0, -sina, -cosa], [0, cosa, -sina]])

    def makeRotationDy(self, alpha):
        sina = math.sin(alpha)
        cosa = math.cos(alpha)
        return Metashape.Matrix([[-sina, 0, cosa], [0, 0, 0], [-cosa, 0, -sina]])

    def makeRotationDz(self, alpha):
        sina = math.sin(alpha)
        cosa = math.cos(alpha)
        return Metashape.Matrix([[-sina, -cosa, 0], [cosa, -sina, 0], [0, 0, 0]])

    def getEulerAnglesName(self, euler_angles):
        if euler_angles == Metashape.EulerAnglesOPK:
            return "OPK"
        if euler_angles == Metashape.EulerAnglesPOK:
            return "POK"
        if euler_angles == Metashape.EulerAnglesYPR:
            return "YPR"
        if euler_angles == Metashape.EulerAnglesANK:
            return "ANK"

    def printVector(self, f, name, value, precision):
        fmt = "{:." + str(precision) + "f}"
        fmt = "    " + name + ": " + fmt + " " + fmt + " " + fmt + "\n"
        f.write(fmt.format(value.x, value.y, value.z))

    def write(self, f):
        euler_name = self.getEulerAnglesName(self.camera.chunk.euler_angles)

        f.write(self.camera.label + "\n")
        if self.reference_location:
            self.printVector(f, "   XYZ source", self.reference_location, 6)
        if self.error_location:
            self.printVector(f, "   XYZ error", self.error_location, 6)
        if self.estimated_location:
            self.printVector(f, "   XYZ estimated", self.estimated_location, 6)
        if self.sigma_location:
            self.printVector(f, "   XYZ sigma", self.sigma_location, 6)
        if self.reference_rotation:
            self.printVector(f, "   " + euler_name + " source", self.reference_rotation, 3)
        if self.error_rotation:
            self.printVector(f, "   " + euler_name + " error", self.error_rotation, 3)
        if self.estimated_rotation:
            self.printVector(f, "   " + euler_name + " estimated", self.estimated_rotation, 3)
        if self.sigma_rotation:
            self.printVector(f, "   " + euler_name + " sigma", self.sigma_rotation, 3)

# %% point_from_RB_centroid_no_filter v1
# def camera_point_from_segment_centerPoint(MetashapeProject_path, Chunk_number, PhotoPath, OutputPath, CenterPoint_path):
    
#     # open metashape project
#     doc = Metashape.Document()
#     doc.open(MetashapeProject_path)

#     photo_fold = (PhotoPath)
#     ts = timestamp()
#     save_path = OutputPath.format(ts)

#     Empty_centroid = []

#     #access metashape chunk
#     chunk = doc.chunks[Chunk_number]
#     T = chunk.transform.matrix
#     crs = chunk.crs

#     # open RB_centroid csv and read as dataframe
#     RB_centroid = pd.read_csv(CenterPoint_path)

#     # ── FIX 1 : CONVERSION CRS AUTOMATIQUE ───────────────────────────────────
#     # Le CSV des centroïdes est toujours en UTM 32737 (coordonnées en mètres).
#     # Si le projet Metashape est en WGS84 (degrés), il faut convertir avant
#     # de chercher les vertices — sinon le code cherche 680460m en degrés → rien trouvé.
#     print(f"\nCRS chunk Metashape : {crs}")

#     csv_is_utm = abs(RB_centroid.center_point_x.mean()) > 180   # UTM = grandes valeurs
#     chunk_is_utm = any(kw in str(crs) for kw in ['UTM', 'Transverse', '32737', '32738'])

#     print(f"CSV en UTM   : {csv_is_utm}")
#     print(f"Chunk en UTM : {chunk_is_utm}")

#     if csv_is_utm and not chunk_is_utm:
#         # CAS DU PROBLÈME : CSV en UTM 32737, chunk en WGS84
#         print("Conversion UTM 32737 -> WGS84 des centroïdes...")
#         utm_crs = Metashape.CoordinateSystem("EPSG::32737")
#         cx_list, cy_list = [], []
#         for _, row in RB_centroid.iterrows():
#             pt = Metashape.Vector((row.center_point_x, row.center_point_y, row.average_z))
#             pt_conv = Metashape.CoordinateSystem.transform(pt, utm_crs, crs)
#             cx_list.append(pt_conv.x)
#             cy_list.append(pt_conv.y)
#         RB_centroid["center_point_x"] = cx_list
#         RB_centroid["center_point_y"] = cy_list
#         print(f"  X apres conversion : {RB_centroid.center_point_x.min():.6f} -> {RB_centroid.center_point_x.max():.6f}")
#         print(f"  Y apres conversion : {RB_centroid.center_point_y.min():.6f} -> {RB_centroid.center_point_y.max():.6f}")
#     else:
#         print("Pas de conversion necessaire — CRS deja compatible")
#     # ─────────────────────────────────────────────────────────────────────────

#     print("Loading model ...")
#     tic = time()

#     #create array of all vertices coordinate from metashape 3d model
#     model = chunk.models[0]
#     v = []
#     v_Trans = []

#     for V in model.vertices:
#         transform_vertices = chunk.crs.project(T.mulp(V.coord))
#         v_Trans.append(transform_vertices)
#         v.append(V.coord)
#     v=np.asarray(v)
#     v_Trans=np.asarray(v_Trans)
#     print("Done in {}".format(convert_time(time()-tic)))

#     #create array of all photo centroid from metashape and apply transformation matrix
#     c = []
#     cams = []
#     c_trans = []

#     for cam in chunk.cameras:
#         try:
#             transform_vertices = chunk.crs.project(T.mulp(cam.center))
#             c_trans.append(transform_vertices)
#             cams.append(cam)
#             c.append(cam.center)
#         except:
#             continue

#     c = np.asarray(c)
#     cams = np.asarray(cams)
#     c_trans = np.asarray(c_trans)

#     # ✅ AJOUT — détection dimensions capteur
#     sensor_w, sensor_h = 7008, 4672
#     for cam in chunk.cameras:
#         if cam.sensor and cam.sensor.width > 0:
#             sensor_w = cam.sensor.width
#             sensor_h = cam.sensor.height
#             break
#     margin = 750

#     out_df_list = []
#     # loop through each SAM centroid
#     for index, row in tqdm(RB_centroid.iterrows(), total=RB_centroid.shape[0]):

#         samID = row.segment_un

#         p = pd.DataFrame({'x': [row.center_point_x],   # ← maintenant en WGS84 grâce au Fix 1
#                           'y': [row.center_point_y],
#                           'z': [-5]})

#         p = np.asarray(p)

#         verts = []

#         eps = 0.002
#         x_condition = np.where(np.logical_and(v_Trans[:,0] > p[0, 0] - eps, v_Trans[:,0] < p[0,0] + eps))
#         y_condition = np.where(np.logical_and(v_Trans[:,1] > p[0, 1] - eps, v_Trans[:,1] < p[0,1] + eps))

#         verts = v_Trans[np.intersect1d(x_condition, y_condition)]
#         if len(verts) == 0:
#             eps = 0.0025
#             x_condition = np.where(np.logical_and(v_Trans[:,0] > p[0, 0] - eps, v_Trans[:,0] < p[0,0] + eps))
#             y_condition = np.where(np.logical_and(v_Trans[:,1] > p[0, 1] - eps, v_Trans[:,1] < p[0,1] + eps))
#             verts = v_Trans[np.intersect1d(x_condition, y_condition)]

#             if len(verts) == 0:
#                 eps = 0.005
#                 x_condition = np.where(np.logical_and(v_Trans[:,0] > p[0, 0] - eps, v_Trans[:,0] < p[0,0] + eps))
#                 y_condition = np.where(np.logical_and(v_Trans[:,1] > p[0, 1] - eps, v_Trans[:,1] < p[0,1] + eps))
#                 verts = v_Trans[np.intersect1d(x_condition, y_condition)]

#                 if len(verts) == 0:
#                     Empty_centroid.append(samID)
#                     continue

#         xy_max_z_arr = max(verts, key=lambda x: x[2])[:]
#         xy_max_z = list(xy_max_z_arr)

#         cam_sub = []
#         cam_UV = []
#         X, Y, Z = (xy_max_z)
#         p = T.inv().mulp(chunk.crs.unproject(Metashape.Vector((X, Y, Z))))

#         for camera in chunk.cameras:
#             try:
#                 # ── FIX 3 : camera.project() appelé UNE SEULE FOIS ──────────
#                 proj = camera.project(p)
#                 if not proj:
#                     continue
#                 u = proj.x
#                 v = proj.y
#                 # ─────────────────────────────────────────────────────────────

#                 if (u < 0 or u > camera.sensor.width or v < 0 or v > camera.sensor.height):
#                     continue

#                 estimated_coord = chunk.crs.project(T.mulp(camera.center))
#                 cam_vec_int = camera.transform.mulv(Metashape.Vector([0, 0, 1]))
#                 cam_vec_ext = chunk.transform.matrix.mulv(cam_vec_int)
#                 cam_vec_ext.normalize()
#                 s1 = Point3D(X, Y, Z)
#                 s2 = Point3D(estimated_coord.x, estimated_coord.y, estimated_coord.z)
#                 distn = (s1.distance(s2))
#                 distn_2d = (s1.distance_2D(s2))
#                 cam_sub.append(camera)
#                 cam_UV.append({'camera_id': camera.label,
#                                'U': u,
#                                'V': v,
#                                'dis_3D': distn,
#                                'dis_2D': distn_2d,
#                                'camera_path': camera.photo.path,
#                                'camera_rotation': CameraStats(camera).estimated_rotation,
#                                'SAM_ID': samID,
#                                'cam_enable': camera.enabled,
#                                'camera_center_coordinate': s2
#                                })
#             except:
#                 continue

#         uv_cam_df = pd.DataFrame(cam_UV)

#         uv_bbox = uv_cam_df[
#             (uv_cam_df["U"] > margin) &
#             (uv_cam_df["U"] < sensor_w - margin) &
#             (uv_cam_df["V"] > margin) &
#             (uv_cam_df["V"] < sensor_h - margin)
#         ]

#         uv_10 = uv_bbox.sort_values(by=['dis_2D', 'dis_3D'], ascending=[True, True]).head(10)

#         for i, r in uv_10.iterrows():
#             cam_id = (r.camera_id + '.JPG')
#             cam_path = r.camera_path
#             out_df_list.append({'SAM_centroid': samID,
#                                 'camera_id': cam_id,
#                                 'camera_path': cam_path,
#                                 'U': r.U,
#                                 'V': r.V,
#                                 'point_x': row.center_point_x,
#                                 'point_y': row.center_point_y,
#                                 'vertex_x': xy_max_z[0],
#                                 'vertex_y': xy_max_z[1],
#                                 'vertex_z': xy_max_z[2],
#                                 'cam_estimated_x': r.camera_center_coordinate.x,
#                                 'cam_estimated_y': r.camera_center_coordinate.y,
#                                 'cam_estimated_z': r.camera_center_coordinate.z,
#                                 'distance_3D_cam_vert': r.dis_3D,
#                                 'distance_2D_cam_vert': r.dis_2D,
#                                 'camera_rotation': r.camera_rotation,
#                                 'camera_yaw': r.camera_rotation[0],
#                                 'camera_pitch': r.camera_rotation[1],
#                                 'camera_roll': r.camera_rotation[2],
#                                 'camera_enable': r.cam_enable
#                                 })

#     camera_UV_csv = pd.DataFrame(out_df_list)

#     # Save csv
#     if not os.path.exists(save_path):
#         camera_UV_csv.to_csv(save_path, index=False)
#     else:
#         camera_UV_csv.to_csv(save_path, mode='a', index=False, header=False)

#     return camera_UV_csv    
#     # open metashape project
#     doc = Metashape.Document()
#     doc.open(MetashapeProject_path)

#     photo_fold = (PhotoPath)
#     ts = timestamp()
#     save_path = OutputPath.format(ts)

#     Empty_centroid = []

#     #access metashape chunk
#     chunk = doc.chunks[Chunk_number]
#     T = chunk.transform.matrix
#     crs = chunk.crs

#     # open RB_centroid csv and read as dataframe
#     RB_centroid = pd.read_csv(CenterPoint_path)

#     # ── FIX 1 : CONVERSION CRS AUTOMATIQUE ───────────────────────────────────
#     # Le CSV des centroïdes est toujours en UTM 32737 (coordonnées en mètres).
#     # Si le projet Metashape est en WGS84 (degrés), il faut convertir avant
#     # de chercher les vertices — sinon le code cherche 680460m en degrés → rien trouvé.
#     print(f"\nCRS chunk Metashape : {crs}")

#     csv_is_utm = abs(RB_centroid.center_point_x.mean()) > 180   # UTM = grandes valeurs
#     chunk_is_utm = any(kw in str(crs) for kw in ['UTM', 'Transverse', '32737', '32738'])

#     print(f"CSV en UTM   : {csv_is_utm}")
#     print(f"Chunk en UTM : {chunk_is_utm}")

#     if csv_is_utm and not chunk_is_utm:
#         # CAS DU PROBLÈME : CSV en UTM 32737, chunk en WGS84
#         print("Conversion UTM 32737 -> WGS84 des centroïdes...")
#         utm_crs = Metashape.CoordinateSystem("EPSG::32737")
#         cx_list, cy_list = [], []
#         for _, row in RB_centroid.iterrows():
#             pt = Metashape.Vector((row.center_point_x, row.center_point_y, row.average_z))
#             pt_conv = Metashape.CoordinateSystem.transform(pt, utm_crs, crs)
#             cx_list.append(pt_conv.x)
#             cy_list.append(pt_conv.y)
#         RB_centroid["center_point_x"] = cx_list
#         RB_centroid["center_point_y"] = cy_list
#         print(f"  X apres conversion : {RB_centroid.center_point_x.min():.6f} -> {RB_centroid.center_point_x.max():.6f}")
#         print(f"  Y apres conversion : {RB_centroid.center_point_y.min():.6f} -> {RB_centroid.center_point_y.max():.6f}")
#     else:
#         print("Pas de conversion necessaire — CRS deja compatible")
#     # ─────────────────────────────────────────────────────────────────────────

#     print("Loading model ...")
#     tic = time()

#     #create array of all vertices coordinate from metashape 3d model
#     model = chunk.models[0]
#     v = []
#     v_Trans = []

#     for V in model.vertices:
#         transform_vertices = chunk.crs.project(T.mulp(V.coord))
#         v_Trans.append(transform_vertices)
#         v.append(V.coord)
#     v=np.asarray(v)
#     v_Trans=np.asarray(v_Trans)
#     print("Done in {}".format(convert_time(time()-tic)))

#     #create array of all photo centroid from metashape and apply transformation matrix
#     c = []
#     cams = []
#     c_trans = []
#     for cam in chunk.cameras:
#         try:
#             transform_vertices = chunk.crs.project(T.mulp(cam.center))
#             c_trans.append(transform_vertices)
#             cams.append(cam)
#             c.append(cam.center)
#         except:
#             continue

#     c = np.asarray(c)
#     cams = np.asarray(cams)
#     c_trans = np.asarray(c_trans)

#     out_df_list = []
#     # loop through each SAM centroid
#     for index, row in tqdm(RB_centroid.iterrows(), total=RB_centroid.shape[0]):

#         samID = row.segment_un

#         p = pd.DataFrame({'x': [row.center_point_x],   # ← maintenant en WGS84 grâce au Fix 1
#                           'y': [row.center_point_y],
#                           'z': [-5]})

#         p = np.asarray(p)

#         verts = []

#         eps = 0.002
#         x_condition = np.where(np.logical_and(v_Trans[:,0] > p[0, 0] - eps, v_Trans[:,0] < p[0,0] + eps))
#         y_condition = np.where(np.logical_and(v_Trans[:,1] > p[0, 1] - eps, v_Trans[:,1] < p[0,1] + eps))

#         verts = v_Trans[np.intersect1d(x_condition, y_condition)]
#         if len(verts) == 0:
#             eps = 0.0025
#             x_condition = np.where(np.logical_and(v_Trans[:,0] > p[0, 0] - eps, v_Trans[:,0] < p[0,0] + eps))
#             y_condition = np.where(np.logical_and(v_Trans[:,1] > p[0, 1] - eps, v_Trans[:,1] < p[0,1] + eps))
#             verts = v_Trans[np.intersect1d(x_condition, y_condition)]

#             if len(verts) == 0:
#                 eps = 0.005
#                 x_condition = np.where(np.logical_and(v_Trans[:,0] > p[0, 0] - eps, v_Trans[:,0] < p[0,0] + eps))
#                 y_condition = np.where(np.logical_and(v_Trans[:,1] > p[0, 1] - eps, v_Trans[:,1] < p[0,1] + eps))
#                 verts = v_Trans[np.intersect1d(x_condition, y_condition)]

#                 if len(verts) == 0:
#                     Empty_centroid.append(samID)
#                     continue

#         xy_max_z_arr = max(verts, key=lambda x: x[2])[:]
#         xy_max_z = list(xy_max_z_arr)

#         cam_sub = []
#         cam_UV = []
#         X, Y, Z = (xy_max_z)
#         p = T.inv().mulp(chunk.crs.unproject(Metashape.Vector((X, Y, Z))))

#         for camera in chunk.cameras:
#             try:
#                 # ── FIX 3 : camera.project() appelé UNE SEULE FOIS ──────────
#                 proj = camera.project(p)
#                 if not proj:
#                     continue
#                 u = proj.x
#                 v = proj.y
#                 # ─────────────────────────────────────────────────────────────

#                 if (u < 0 or u > camera.sensor.width or v < 0 or v > camera.sensor.height):
#                     continue

#                 estimated_coord = chunk.crs.project(T.mulp(camera.center))
#                 cam_vec_int = camera.transform.mulv(Metashape.Vector([0, 0, 1]))
#                 cam_vec_ext = chunk.transform.matrix.mulv(cam_vec_int)
#                 cam_vec_ext.normalize()
#                 s1 = Point3D(X, Y, Z)
#                 s2 = Point3D(estimated_coord.x, estimated_coord.y, estimated_coord.z)
#                 distn = (s1.distance(s2))
#                 distn_2d = (s1.distance_2D(s2))
#                 cam_sub.append(camera)
#                 cam_UV.append({'camera_id': camera.label,
#                                'U': u,
#                                'V': v,
#                                'dis_3D': distn,
#                                'dis_2D': distn_2d,
#                                'camera_path': camera.photo.path,
#                                'camera_rotation': CameraStats(camera).estimated_rotation,
#                                'SAM_ID': samID,
#                                'cam_enable': camera.enabled,
#                                'camera_center_coordinate': s2
#                                })
#             except:
#                 continue

#         uv_cam_df = pd.DataFrame(cam_UV)

#         uv_bbox = uv_cam_df[(uv_cam_df["U"] > 750) & (uv_cam_df["U"] < 7506) & (uv_cam_df["V"] > 750) & (uv_cam_df["V"] < 4754)]
#         uv_10 = uv_bbox.sort_values(by=['dis_2D', 'dis_3D'], ascending=[True, True]).head(10)

#         for i, r in uv_10.iterrows():
#             cam_id = (r.camera_id + '.JPG')
#             cam_path = r.camera_path
#             out_df_list.append({'SAM_centroid': samID,
#                                 'camera_id': cam_id,
#                                 'camera_path': cam_path,
#                                 'U': r.U,
#                                 'V': r.V,
#                                 'point_x': row.center_point_x,
#                                 'point_y': row.center_point_y,
#                                 'vertex_x': xy_max_z[0],
#                                 'vertex_y': xy_max_z[1],
#                                 'vertex_z': xy_max_z[2],
#                                 'cam_estimated_x': r.camera_center_coordinate.x,
#                                 'cam_estimated_y': r.camera_center_coordinate.y,
#                                 'cam_estimated_z': r.camera_center_coordinate.z,
#                                 'distance_3D_cam_vert': r.dis_3D,
#                                 'distance_2D_cam_vert': r.dis_2D,
#                                 'camera_rotation': r.camera_rotation,
#                                 'camera_yaw': r.camera_rotation[0],
#                                 'camera_pitch': r.camera_rotation[1],
#                                 'camera_roll': r.camera_rotation[2],
#                                 'camera_enable': r.cam_enable
#                                 })

#     camera_UV_csv = pd.DataFrame(out_df_list)

#     # Save csv
#     if not os.path.exists(save_path):
#         camera_UV_csv.to_csv(save_path, index=False)
#     else:
#         camera_UV_csv.to_csv(save_path, mode='a', index=False, header=False)

#     return camera_UV_csv

# v2
def camera_point_from_segment_centerPoint(MetashapeProject_path, Chunk_number, PhotoPath, OutputPath, CenterPoint_path):
    
    import concurrent.futures
    
    doc = Metashape.Document()
    doc.open(MetashapeProject_path)

    photo_fold = (PhotoPath)
    ts = timestamp()
    save_path = OutputPath.format(ts) if '{}' in OutputPath else OutputPath

    Empty_centroid = []

    chunk = doc.chunks[Chunk_number]
    T = chunk.transform.matrix
    crs = chunk.crs

    RB_centroid = pd.read_csv(CenterPoint_path)

    # ── FIX 1 : CONVERSION CRS ───────────────────────────────────────────────
    print(f"\nCRS chunk Metashape : {crs}")
    csv_is_utm   = abs(RB_centroid.center_point_x.mean()) > 180
    chunk_is_utm = any(kw in str(crs) for kw in ['UTM', 'Transverse', '32737', '32738'])
    print(f"CSV en UTM   : {csv_is_utm}")
    print(f"Chunk en UTM : {chunk_is_utm}")

    if csv_is_utm and not chunk_is_utm:
        print("Conversion UTM 32737 -> WGS84 des centroides...")
        utm_crs = Metashape.CoordinateSystem("EPSG::32737")
        cx_list, cy_list = [], []
        for _, row in RB_centroid.iterrows():
            pt      = Metashape.Vector((row.center_point_x, row.center_point_y, row.average_z))
            pt_conv = Metashape.CoordinateSystem.transform(pt, utm_crs, crs)
            cx_list.append(pt_conv.x)
            cy_list.append(pt_conv.y)
        RB_centroid["center_point_x"] = cx_list
        RB_centroid["center_point_y"] = cy_list
        print(f"  X : {RB_centroid.center_point_x.min():.6f} -> {RB_centroid.center_point_x.max():.6f}")
        print(f"  Y : {RB_centroid.center_point_y.min():.6f} -> {RB_centroid.center_point_y.max():.6f}")
    else:
        print("Pas de conversion necessaire")
    # ─────────────────────────────────────────────────────────────────────────

    print("Loading model ...")
    tic = time()
    model   = chunk.models[0]
    v       = []
    v_Trans = []
    for V in model.vertices:
        transform_vertices = chunk.crs.project(T.mulp(V.coord))
        v_Trans.append(transform_vertices)
        v.append(V.coord)
    v       = np.asarray(v)
    v_Trans = np.asarray(v_Trans)
    print("Done in {}".format(convert_time(time()-tic)))

    # ── Pré-calcul caméras ───────────────────────────────────────────────────
    c       = []
    cams    = []
    c_trans = []
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

    # ── FIX 2 : DIMENSIONS CAPTEUR ───────────────────────────────────────────
    sensor_w, sensor_h = 7008, 4672
    for cam in chunk.cameras:
        if cam.sensor and cam.sensor.width > 0:
            sensor_w = cam.sensor.width
            sensor_h = cam.sensor.height
            print(f"Capteur : {sensor_w} x {sensor_h} px")
            break
    margin = 300

    # Liste des caméras alignées — pré-calculée une seule fois
    cams_alignees = [cam for cam in chunk.cameras if cam.transform]
    print(f"Cameras valides : {len(cams_alignees)}")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Fonction de projection sur une caméra (appelée en parallèle) ─────────
    def projet_camera(args):
        camera, p_vec, X, Y, Z, samID = args
        try:
            proj = camera.project(p_vec)
            if not proj:
                return None
            u = proj.x
            v = proj.y
            if (u < 0 or u > camera.sensor.width or
                v < 0 or v > camera.sensor.height):
                return None

            estimated_coord = chunk.crs.project(T.mulp(camera.center))
            s1 = Point3D(X, Y, Z)
            s2 = Point3D(estimated_coord.x, estimated_coord.y, estimated_coord.z)
            distn    = s1.distance(s2)
            distn_2d = s1.distance_2D(s2)

            return {
                'camera_id'               : camera.label,
                'U'                       : u,
                'V'                       : v,
                'dis_3D'                  : distn,
                'dis_2D'                  : distn_2d,
                'camera_path'             : camera.photo.path,
                'camera_rotation'         : CameraStats(camera).estimated_rotation,
                'SAM_ID'                  : samID,
                'cam_enable'              : camera.enabled,
                'camera_center_coordinate': s2
            }
        except:
            return None
    # ─────────────────────────────────────────────────────────────────────────

    out_df_list = []

    # ── Boucle principale avec tqdm ───────────────────────────────────────────
    for index, row in tqdm(RB_centroid.iterrows(), total=RB_centroid.shape[0]):

        samID = row.segment_un

        p = pd.DataFrame({'x': [row.center_point_x],
                          'y': [row.center_point_y],
                          'z': [-5]})
        p = np.asarray(p)

        # ── FIX 3 : EPS PROGRESSIF ───────────────────────────────────────────
        verts = np.array([])
        for eps in [0.00001, 0.00002, 0.00005]:
            x_condition = np.where(np.logical_and(
                v_Trans[:,0] > p[0, 0] - eps,
                v_Trans[:,0] < p[0, 0] + eps))
            y_condition = np.where(np.logical_and(
                v_Trans[:,1] > p[0, 1] - eps,
                v_Trans[:,1] < p[0, 1] + eps))
            verts = v_Trans[np.intersect1d(x_condition, y_condition)]
            if len(verts) > 0:
                break

        if len(verts) == 0:
            Empty_centroid.append(samID)
            continue
        # ─────────────────────────────────────────────────────────────────────

        xy_max_z_arr = max(verts, key=lambda x: x[2])[:]
        xy_max_z     = list(xy_max_z_arr)
        X, Y, Z      = xy_max_z
        p_vec        = T.inv().mulp(chunk.crs.unproject(Metashape.Vector((X, Y, Z))))

        # ── Parallélisation de la projection sur les caméras ─────────────────
        args_list = [(cam, p_vec, X, Y, Z, samID) for cam in cams_alignees]

        cam_UV = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = executor.map(projet_camera, args_list)
            for res in results:
                if res is not None:
                    cam_UV.append(res)
        # ─────────────────────────────────────────────────────────────────────

        if not cam_UV:
            Empty_centroid.append(samID)
            continue

        uv_cam_df = pd.DataFrame(cam_UV)

        # ── FIX 4 : BBOX DYNAMIQUE ───────────────────────────────────────────
        uv_bbox = uv_cam_df[
            (uv_cam_df["U"] > margin) &
            (uv_cam_df["U"] < sensor_w - margin) &
            (uv_cam_df["V"] > margin) &
            (uv_cam_df["V"] < sensor_h - margin)
        ]
        if uv_bbox.empty:
            uv_bbox = uv_cam_df
        # ─────────────────────────────────────────────────────────────────────

        uv_10 = uv_bbox.sort_values(
            by=['dis_2D', 'dis_3D'],
            ascending=[True, True]
        ).head(10)

        for i, r in uv_10.iterrows():
            cam_id   = (r.camera_id + '.JPG')
            cam_path = r.camera_path
            out_df_list.append({
                'SAM_centroid'            : samID,
                'camera_id'               : cam_id,
                'camera_path'             : cam_path,
                'U'                       : r.U,
                'V'                       : r.V,
                'point_x'                 : row.center_point_x,
                'point_y'                 : row.center_point_y,
                'vertex_x'                : xy_max_z[0],
                'vertex_y'                : xy_max_z[1],
                'vertex_z'                : xy_max_z[2],
                'cam_estimated_x'         : r.camera_center_coordinate.x,
                'cam_estimated_y'         : r.camera_center_coordinate.y,
                'cam_estimated_z'         : r.camera_center_coordinate.z,
                'distance_3D_cam_vert'    : r.dis_3D,
                'distance_2D_cam_vert'    : r.dis_2D,
                'camera_rotation'         : r.camera_rotation,
                'camera_yaw'              : r.camera_rotation[0],
                'camera_pitch'            : r.camera_rotation[1],
                'camera_roll'             : r.camera_rotation[2],
                'camera_enable'           : r.cam_enable
            })

    print(f"\nSegments sans vertex : {len(Empty_centroid)}")

    camera_UV_csv = pd.DataFrame(out_df_list)

    if not os.path.exists(save_path):
        camera_UV_csv.to_csv(save_path, index=False)
    else:
        camera_UV_csv.to_csv(save_path, mode='a', index=False, header=False)

    return camera_UV_csv

#%% HexaGrid functions

def create_hexagon(l, x, y):
    """
    Create a hexagon centered on (x, y)
    :param l: length of the hexagon's edge
    :param x: x-coordinate of the hexagon's center
    :param y: y-coordinate of the hexagon's center
    :return: The polygon containing the hexagon's coordinates
    """
    c = [[x + math.cos(math.radians(angle)) * l, y + math.sin(math.radians(angle)) * l] for angle in range(0, 360, 60)]
    return Polygon(c)

def create_hexgrid(bbox, side):
    """
    returns an array of Points describing hexagons centers that are inside the given bounding_box
    :param bbox: The containing bounding box. The bbox coordinate should be in Webmercator.
    :param side: The size of the hexagons'
    :return: The hexagon grid
    """
    grid = []

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

def hexagrid(ortho, resolution, full_grid_path, segments_df_filtered, clip_grid_path, hexagrid_SAM_union_path_seg_shp, hexagrid_SAM_union_pst_shp, hexagrid_SAM_union_path_pts_csv ):
    #Get orthomosaic extentand create hexa grid

    dataset = rasterio.open(ortho)
    Res = resolution
    edge = math.sqrt(Res**2/(3/2 * math.sqrt(3)))
    hex_centers = create_hexgrid(dataset.bounds, edge)
    hexa = ([create_hexagon(edge, center[0], center[1]) for center in hex_centers])
    
    # clip Hexagrid with SAM shp filtered
    p = gpd.GeoSeries(hexa)
    
    hexagrid = gpd.GeoDataFrame(geometry=gpd.GeoSeries(p))
    hexagrid.to_file(full_grid_path)
    segments = gpd.read_file(segments_df_filtered)
    hexagrid_segments_df_filtered_difference = hexagrid.overlay(segments, how='difference')
    hexagrid_segments_df_filtered_difference['segment_un']=hexagrid_segments_df_filtered_difference.index
    hexagrid_segments_df_filtered_difference['segment_un'] = 'Hexa_' + hexagrid_segments_df_filtered_difference['segment_un'].astype(str)
    hexagrid_segments_df_filtered_difference['area']= hexagrid_segments_df_filtered_difference.area
    hexagrid_segments_df_filtered_difference.to_file(clip_grid_path)

    #hexagrid_segments_df_filtered_difference=hexagrid_segments_df_filtered_difference.drop(['FID'], axis = 1)
    segments2 = segments[['geometry', 'segment_un', 'area']]
    hexagrid_SAM = gpd.GeoDataFrame(pd.concat([segments2, hexagrid_segments_df_filtered_difference]))
    
    
    # get center point xy coordinate
    
    RB_shp_df = gpd.GeoDataFrame(hexagrid_SAM, geometry='geometry')
    RB_shp_df = RB_shp_df[RB_shp_df['area'] > 0]
    RB_shp_df['center_point'] = RB_shp_df.representative_point()
    RB_shp_df['area'] = RB_shp_df.area
    RB_shp_df['center_point_x'] = RB_shp_df.center_point.apply(lambda p :p.x)
    RB_shp_df['center_point_y'] = RB_shp_df.center_point.apply(lambda p :p.y)
    RB_shp_df['average_z'] = -5
    RB_pts_df = RB_shp_df.drop(['geometry'], axis=1)
    RB_pts_df = gpd.GeoDataFrame(RB_pts_df, geometry='center_point')

    RB_pts_df.to_file(hexagrid_SAM_union_pst_shp)
    RB_pts_df.to_csv(hexagrid_SAM_union_path_pts_csv )

    RB_shp_df = RB_shp_df.drop(['center_point'], axis=1)
    RB_shp_df.to_file(hexagrid_SAM_union_path_seg_shp)

    return RB_shp_df, RB_pts_df