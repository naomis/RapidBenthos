from RB_fcn_part3 import Select_class_ReefCloud_pts, format_percent_cover, stack_catplot, rgb_to_hex, ColonyLevel_Segments
import matplotlib.pyplot as plt
RB_centroid_csv = r"\\Creo34-nas\creo\CTI_Detourgage-automatise\recap desktop\RapidBenthos_Data\outputs\M7_Reoriented\M7_EPSG32737_reoriented_5mm\M7_reoriented5mm.csv"

 


# ============================================================
# INPUTS
# ============================================================
RB_centroid_csv = r"\\Creo34-nas\creo\CTI_Detourgage-automatise\recap desktop\RapidBenthos_Data\outputs\M7_Reoriented\M7_EPSG32737_reoriented_5mm\M7_reoriented5mm.csv"

RC_csv = r"C:\Users\CMBU\Desktop\dense_inference\results\SAM_points\M7_reoriented5mm\M7_reoriented5mm_2026-06-29_14-33-10.csv"

label_file = r"C:\Users\CMBU\Desktop\RapidBenthos\label_set_M7_compatible.csv"

polygon_file = r"\\Creo34-nas\creo\CTI_Detourgage-automatise\recap desktop\RapidBenthos_Data\outputs\M7_Reoriented\M7_EPSG32737_reoriented_5mm\M7Reoriented2026-06-12_hex_seg.shp"

label_polygon_seg       = r"C:\Users\CMBU\Desktop\RapidBenthos\M7 reo\M75mm_labeled_segments.shp"
label_poygon_csv        = r"C:\Users\CMBU\Desktop\RapidBenthos\M7 reo\M75mm_labeled_segments.csv"
PercentCover            = r"C:\Users\CMBU\Desktop\RapidBenthos\M7 reo\M75mm_percent_cover.csv"
out_fig                 = r"C:\Users\CMBU\Desktop\RapidBenthos\M7 reo\M75mm_community_composition.png"
ColonyLevelSegments_shp = r"C:\Users\CMBU\Desktop\RapidBenthos\M7 reo\M75mm_colony_segments.shp"
# ============================================================
# OBLIGATOIRE SUR WINDOWS pour multiprocessing
# ============================================================
if __name__ == '__main__':

    # ÉTAPE 1
    gdf = Select_class_ReefCloud_pts(
        RB_centroid_csv, RC_csv, label_file,
        polygon_file, label_polygon_seg, label_poygon_csv
    )

    # ÉTAPE 2
    RB_shp_df_classes_result_group_morpho, palette_RB = format_percent_cover(label_polygon_seg, label_file)
    RB_shp_df_classes_result_group_morpho.to_csv(PercentCover)
    RB_shp_df_classes_result_group_morpho['Morphology'] = \
        RB_shp_df_classes_result_group_morpho['Morphology'].replace(
            {'Columnar (CAAB 11 290915)': 'Columnar'}
        )
    Class_order = [
        'Acropora Corymbose (ACO)', 'Acropora', 'Branching_non_acropora',
        'Massive', 'Foliose', 'Encrusting', 'Columnar', 'Fire_Coral',
        'Fungiidae', 'Soft_Coral', 'Sponge', 'Algae',
        'Abiotic_substrate', 'Mobile_Biota', 'Markers', 'Unidentifiable'
    ]

    # ÉTAPE 3
    fi2 = plt.figure(figsize=(6, 3), dpi=600)
    stack_catplot(
        x='Morphology', y='Percent_cover',
        cat='treatment', stack='label_set',
        data=RB_shp_df_classes_result_group_morpho,
        palette=palette_RB, out_fig=out_fig, order=Class_order
    )

    # ÉTAPE 4
    gdf_colonyLevel = ColonyLevel_Segments(label_polygon_seg, ColonyLevelSegments_shp)

    print("✅ Part 3 terminée !")
    print(f"   → Segments classifiés : {label_polygon_seg}")
    print(f"   → Pourcentage cover   : {PercentCover}")
    print(f"   → Graphique           : {out_fig}")
    print(f"   → Colonies            : {ColonyLevelSegments_shp}")