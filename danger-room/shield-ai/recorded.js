/* Original recorded 12 October native execution receipt and capture templates, preserved from danger-room/index.html. */
globalThis.DR_RECORDED = {
  "run": {
    "schema": "danger-room-collaborator-demo@1",
    "run_utc": "2026-10-12T08:34:43.419135+00:00",
    "source_commit": "9f3df5c348449d09c7a83cd00e4bd030e075dc92",
    "source_sha256": {
      "src/axm_embodied/danger_room.py": "e61b0de215f6e47a869eacae83d1e3424d26158c6c9caa1be8f92f76cf99e5ed",
      "src/axm_embodied/fly0.py": "c13310ce52ee4ad2adc691df9acec2f2ca87b1f07cc16eaaa0a841c0c657f3f9"
    },
    "python": "3.13.15",
    "dependency": "click==8.1.8 installed only into temporary directory and removed after execution",
    "evidence_class": "synthetic_training_not_physical",
    "controller": "fly0@1 baseline; not the newer 12A learned support-state head",
    "scenario": {
      "agents": 2,
      "ticks": 260,
      "dt_seconds": 0.1,
      "seed": 5,
      "dropout_agent": "node-01",
      "dropout_start_tick": 40,
      "dropout_end_tick_exclusive": 80
    },
    "checks": {
      "ledger_and_world_replay": "PASS",
      "fresh_controller_execution_ledger_byte_equal": true,
      "loopback_tcp_actions_equal": true,
      "tcp_ledger_and_world_replay": "PASS",
      "adapter_errors": 0,
      "tampered_ledger_rejected": true,
      "tamper_error": "hash mismatch at row 51"
    },
    "first_hold_tick_during_dropout": 55,
    "ledger_sha256": "851bda84d3267a1dcc1ea74eaed38d67a629a7374fbd25e68c86ecf2e0f5c479",
    "wall_seconds_first_run": 0.0919112,
    "virtual_seconds": 26,
    "sample_columns": [
      "tick",
      "node1_x_after",
      "node1_y_after",
      "node2_x_after",
      "node2_y_after",
      "node1_confidence",
      "node1_hold",
      "node1_navigation_cue_present"
    ],
    "samples": [
      [
        0,
        84.866814,
        53.050451,
        15.60531,
        46.957969,
        255,
        false,
        true
      ],
      [
        10,
        84.862508,
        53.023189,
        20.493483,
        47.269767,
        255,
        false,
        true
      ],
      [
        20,
        82.475739,
        51.730542,
        25.461821,
        47.700699,
        255,
        false,
        true
      ],
      [
        30,
        77.744587,
        51.13903,
        30.438107,
        48.144087,
        255,
        false,
        true
      ],
      [
        39,
        73.282868,
        50.809585,
        34.916684,
        48.544037,
        255,
        false,
        true
      ],
      [
        40,
        72.816266,
        50.77755,
        35.414304,
        48.588476,
        239,
        false,
        false
      ],
      [
        50,
        69.865494,
        50.578184,
        40.3905,
        49.032866,
        79,
        false,
        false
      ],
      [
        54,
        69.560576,
        50.557777,
        42.380958,
        49.21086,
        15,
        false,
        false
      ],
      [
        55,
        69.560576,
        50.557777,
        42.878569,
        49.255394,
        0,
        true,
        false
      ],
      [
        56,
        69.560576,
        50.557777,
        43.37618,
        49.299929,
        0,
        true,
        false
      ],
      [
        60,
        69.560576,
        50.557777,
        45.366625,
        49.478066,
        0,
        true,
        false
      ],
      [
        70,
        69.560576,
        50.557777,
        50.342715,
        49.923648,
        0,
        true,
        false
      ],
      [
        79,
        69.560576,
        50.557777,
        54.821138,
        50.325316,
        0,
        true,
        false
      ],
      [
        80,
        69.061988,
        50.524458,
        55.318741,
        50.369946,
        255,
        false,
        true
      ],
      [
        81,
        68.563297,
        50.49118,
        55.816343,
        50.414576,
        255,
        false,
        true
      ],
      [
        90,
        64.075079,
        50.191676,
        60.294702,
        50.816959,
        255,
        false,
        true
      ],
      [
        100,
        59.088161,
        49.859038,
        65.271219,
        51.26561,
        255,
        false,
        true
      ],
      [
        110,
        54.101188,
        49.527212,
        70.248175,
        51.71608,
        255,
        false,
        true
      ],
      [
        120,
        49.114216,
        49.195387,
        75.225667,
        52.168379,
        255,
        false,
        true
      ],
      [
        130,
        44.127243,
        48.863561,
        80.203046,
        52.621918,
        255,
        false,
        true
      ],
      [
        140,
        39.140216,
        48.532548,
        83.240464,
        52.899772,
        255,
        false,
        true
      ],
      [
        150,
        34.15318,
        48.201679,
        84.29961,
        52.997005,
        255,
        false,
        true
      ],
      [
        160,
        29.166097,
        47.871527,
        84.622635,
        53.026841,
        255,
        false,
        true
      ],
      [
        170,
        24.178969,
        47.542044,
        84.622635,
        53.026841,
        255,
        false,
        true
      ],
      [
        180,
        19.234853,
        47.216827,
        84.622635,
        53.026841,
        255,
        false,
        true
      ],
      [
        190,
        16.563558,
        47.042153,
        84.622635,
        53.026841,
        255,
        false,
        true
      ],
      [
        200,
        15.632099,
        46.982001,
        84.622635,
        53.026841,
        255,
        false,
        true
      ],
      [
        210,
        15.372031,
        46.965345,
        84.622635,
        53.026841,
        255,
        true,
        true
      ],
      [
        220,
        15.372031,
        46.965345,
        84.622635,
        53.026841,
        255,
        true,
        true
      ],
      [
        230,
        15.372031,
        46.965345,
        84.622635,
        53.026841,
        255,
        true,
        true
      ],
      [
        240,
        15.372031,
        46.965345,
        84.622635,
        53.026841,
        255,
        true,
        true
      ],
      [
        250,
        15.372031,
        46.965345,
        84.622635,
        53.026841,
        255,
        true,
        true
      ],
      [
        259,
        15.372031,
        46.965345,
        84.622635,
        53.026841,
        255,
        true,
        true
      ]
    ],
    "limits": [
      "Synthetic point-world baseline, not flight dynamics or camera demonstration.",
      "Hold means zero synthetic velocity; physical stopping is not tested.",
      "TCP exercised on loopback on one host, not a Raspberry Pi.",
      "Full rerun equality tested on this interpreter and host only.",
      "Viewer samples are extracted from the executed trace, not a full log.",
      "The hash-chained run is not a signed Genesis shard."
    ]
  },
  "assets": {
    "session.template.json": "{\n  \"schema\": \"danger-room-camera-capture-request@1 (proposed interchange only)\",\n  \"session_id\": null,\n  \"evidence_class\": null,\n  \"recording_context\": {\n    \"type\": null,\n    \"notes\": \"bench | PX4 SITL/SIH | HITL | physical flight; describe actual test performed\"\n  },\n  \"flight_controller\": {\n    \"model\": null,\n    \"firmware_name\": null,\n    \"firmware_version_or_hash\": null,\n    \"link_to_pi\": null\n  },\n  \"companion\": {\n    \"board\": null,\n    \"os_and_version\": null,\n    \"software_repo_revision\": null\n  },\n  \"camera\": {\n    \"model\": null,\n    \"interface\": null,\n    \"capture_api\": null,\n    \"nominal_fps\": null,\n    \"width_px\": null,\n    \"height_px\": null,\n    \"frame_seq_source\": null,\n    \"camera_timestamp_source\": null\n  },\n  \"clock_domains\": {\n    \"pi_clock_id\": \"CLOCK_MONOTONIC (example; specify actual)\",\n    \"camera_clock_id\": null,\n    \"fc_clock_id\": null,\n    \"sync_method\": null,\n    \"measured_offset_or_mapping\": null,\n    \"sync_uncertainty_ns\": null\n  },\n  \"experiment\": {\n    \"event_of_interest\": null,\n    \"expected_detection\": null,\n    \"controller_action_allowed\": null,\n    \"recording_start_utc_if_known\": null\n  },\n  \"artifacts\": {\n    \"camera_media\": null,\n    \"frames_csv\": null,\n    \"flight_log_ulg_or_tlog\": null,\n    \"decision_log_csv\": null,\n    \"notes\": null\n  },\n  \"privacy\": {\n    \"location_redacted\": null,\n    \"other_redactions\": null\n  }\n}\n",
    "frames.template.csv": "session_id,frame_seq,camera_timestamp_ns,camera_clock_id,pi_received_monotonic_ns,consumer_seen_monotonic_ns,status,image_ref,notes\n",
    "frames.SYNTHETIC_EXAMPLE.csv": "session_id,frame_seq,camera_timestamp_ns,camera_clock_id,pi_received_monotonic_ns,consumer_seen_monotonic_ns,status,image_ref,notes\nEXAMPLE-ONLY,100,1000000000,CAMERA_PTS,5000000000,5006000000,delivered,video.mp4#frame=100,SYNTHETIC; clocks not aligned\nEXAMPLE-ONLY,101,1033333333,CAMERA_PTS,5035000000,5041000000,delivered,video.mp4#frame=101,SYNTHETIC\nEXAMPLE-ONLY,102,1066666666,CAMERA_PTS,5068000000,5075000000,delivered,video.mp4#frame=102,SYNTHETIC\nEXAMPLE-ONLY,103,,,,,absent_in_sequence,,\"SYNTHETIC; gap inferred from trustworthy source IDs, point of loss unknown\"\nEXAMPLE-ONLY,104,1133333333,CAMERA_PTS,5220000000,5227000000,arrived_after_newer_frame,video.mp4#frame=104,SYNTHETIC; 105 and 106 appeared at the Pi first\nEXAMPLE-ONLY,105,1166666666,CAMERA_PTS,5170000000,5177000000,delivered,video.mp4#frame=105,SYNTHETIC\nEXAMPLE-ONLY,106,1200000000,CAMERA_PTS,5200000000,5207000000,delivered,video.mp4#frame=106,SYNTHETIC\n",
    "decisions.template.csv": "session_id,decision_seq,decision_pi_monotonic_ns,last_frame_seq,last_frame_pi_received_monotonic_ns,support_state,command_or_action,reason,notes\n",
    "telemetry.template.csv": "session_id,pi_received_monotonic_ns,autopilot_time_us,message_name,field_name,value,unit,notes\n"
  }
};

