def prepare_pipeline_move(text: str) -> dict:
    return {
        "kind": "pipeline",
        "requested_change": text,
        "dry_run_action": "would_move_ghl_pipeline_stage",
    }
