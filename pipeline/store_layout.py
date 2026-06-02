"""
Store zone layout configuration.

Defines polygon zones for each camera in the Brigade Road store.
Used by zone_mapper.py to determine which zone a person is in.
"""

STORE_LAYOUT = {
    "store_id": "STORE_BLR_002",
    "store_name": "Brigade Road Bangalore",
    "cameras": {
        "CAM_01": {
            "source": "CAM 1.mp4",
            "type": "entry_exit",
            "zones": {
                "ENTRY_EXIT": {
                    "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                    "description": "Store entrance/exit area"
                }
            }
        },
        "CAM_02": {
            "source": "CAM 2.mp4",
            "type": "main_floor",
            "zones": {
                "SKINCARE": {
                    "polygon": [[0, 0], [320, 0], [320, 480], [0, 480]],
                    "description": "Skincare product zone (left half)"
                },
                "MAKEUP": {
                    "polygon": [[320, 0], [640, 0], [640, 480], [320, 480]],
                    "description": "Makeup product zone (right half)"
                }
            }
        },
        "CAM_03": {
            "source": "CAM 3.mp4",
            "type": "main_floor",
            "zones": {
                "BATH_BODY": {
                    "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                    "description": "Bath & Body product zone"
                }
            }
        },
        "CAM_04": {
            "source": "CAM 4.mp4",
            "type": "billing",
            "zones": {
                "BILLING": {
                    "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
                    "description": "Billing counter area"
                }
            }
        },
        "CAM_05": {
            "source": "CAM 5.mp4",
            "type": "overview",
            "zones": {
                "SKINCARE": {
                    "polygon": [[0, 0], [213, 0], [213, 480], [0, 480]],
                    "description": "Skincare section (overview)"
                },
                "MAKEUP": {
                    "polygon": [[213, 0], [426, 0], [426, 480], [213, 480]],
                    "description": "Makeup section (overview)"
                },
                "BATH_BODY": {
                    "polygon": [[426, 0], [640, 0], [640, 480], [426, 480]],
                    "description": "Bath & Body section (overview)"
                }
            }
        }
    }
}
