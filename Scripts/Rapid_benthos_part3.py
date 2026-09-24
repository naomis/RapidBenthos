import os
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from RB_paths import get_part3_inputs
from RB_fcn_part3 import (
    ColonyLevel_Segments,
    Select_class_ReefCloud_pts,
    format_percent_cover,
    rgb_to_hex,
    stack_catplot,
)

paths = get_part3_inputs()

RB_centroid_csv = paths["rb_centroid_csv"]
RC_csv = paths["rc_csv"]
label_file = paths["label_file"]
polygon_file = paths["polygon_file"]
label_polygon_seg = paths["label_polygon_seg"]
label_poygon_csv = paths["label_polygon_csv"]
PercentCover = paths["percent_cover"]
out_fig = paths["out_fig"]
ColonyLevelSegments_shp = paths["colony_segments_shp"]

# ============================================================
# OBLIGATOIRE SUR WINDOWS pour multiprocessing
# ============================================================
if __name__ == "__main__":
    # ÉTAPE 1
    gdf = Select_class_ReefCloud_pts(
        RB_centroid_csv,
        RC_csv,
        label_file,
        polygon_file,
        label_polygon_seg,
        label_poygon_csv,
    )

    # ÉTAPE 2
    RB_shp_df_classes_result_group_morpho, palette_RB = format_percent_cover(
        label_polygon_seg, label_file
    )
    RB_shp_df_classes_result_group_morpho.to_csv(PercentCover)
    RB_shp_df_classes_result_group_morpho["Morphology"] = (
        RB_shp_df_classes_result_group_morpho["Morphology"].replace(
            {"Columnar (CAAB 11 290915)": "Columnar"}
        )
    )
    Class_order = [
        "Acropora Corymbose (ACO)",
        "Acropora",
        "Branching_non_acropora",
        "Massive",
        "Foliose",
        "Encrusting",
        "Columnar",
        "Fire_Coral",
        "Fungiidae",
        "Soft_Coral",
        "Sponge",
        "Algae",
        "Abiotic_substrate",
        "Mobile_Biota",
        "Markers",
        "Unidentifiable",
    ]

    # ÉTAPE 3
    fi2 = plt.figure(figsize=(6, 3), dpi=600)
    stack_catplot(
        x="Morphology",
        y="Percent_cover",
        cat="treatment",
        stack="label_set",
        data=RB_shp_df_classes_result_group_morpho,
        palette=palette_RB,
        out_fig=out_fig,
        order=Class_order,
    )

    # ÉTAPE 4
    gdf_colonyLevel = ColonyLevel_Segments(label_polygon_seg, ColonyLevelSegments_shp)

    print("✅ Part 3 terminée !")
    print(f"   → Segments classifiés : {label_polygon_seg}")
    print(f"   → Pourcentage cover   : {PercentCover}")
    print(f"   → Graphique           : {out_fig}")
    print(f"   → Colonies            : {ColonyLevelSegments_shp}")
