def prepare_follow_up(text: str) -> dict:
    return {
        "kind": "follow_up",
        "draft": f"Following up on: {text}",
        "dry_run_action": "would_send_follow_up_after_approval",
    }
