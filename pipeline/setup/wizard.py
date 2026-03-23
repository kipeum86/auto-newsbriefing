"""Interactive setup wizard for auto-newsbriefing."""

import os
import sys

import yaml


def run_wizard(config_path: str = "config.yaml", from_example: bool = False):
    """Interactive CLI wizard to generate config.yaml."""
    print("\n=== auto-newsbriefing Setup Wizard ===\n")

    config: dict = {}

    if from_example and os.path.isfile("config.example.yaml"):
        with open("config.example.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        print("Loaded config.example.yaml as starting point.\n")

    # Step 1: Validate API keys
    print("--- Step 1: API Key Validation ---")
    provider = _ask("LLM provider (claude/openai/gemini)", default="claude")
    config.setdefault("llm", {})["provider"] = provider
    _validate_keys(provider)

    # Step 2: Domain
    print("\n--- Step 2: Domain Settings ---")
    name = _ask("Domain name (e.g., 핀테크, 의료, 게임)")
    desc = _ask("Domain description (e.g., 핀테크 규제 동향 브리핑)")
    lang = _ask("Output language", default="ko")
    config["domain"] = {"name": name, "description": desc, "language": lang}

    # Step 3: Categories
    print("\n--- Step 3: Categories ---")
    print("Enter categories (empty name to stop):")
    categories = []
    while True:
        cat_name = _ask(f"  Category {len(categories)+1} name", allow_empty=True)
        if not cat_name:
            break
        cat_desc = _ask(f"  Category {len(categories)+1} description", allow_empty=True)
        categories.append({"name": cat_name, "description": cat_desc})
    config["categories"] = categories

    # Step 4: Keywords
    print("\n--- Step 4: Keywords ---")
    include = _ask("Include keywords (comma-separated)", allow_empty=True)
    exclude = _ask("Exclude keywords (comma-separated)", allow_empty=True)
    config["keywords"] = {
        "include": [k.strip() for k in include.split(",") if k.strip()] if include else [],
        "exclude": [k.strip() for k in exclude.split(",") if k.strip()] if exclude else [],
    }

    # Step 5: RSS Sources
    print("\n--- Step 5: RSS Sources ---")
    print("Enter tier_a sources (reliable, empty URL to stop):")
    tier_a = _collect_sources()
    print("Enter tier_b sources (unreliable, empty URL to stop):")
    tier_b = _collect_sources()
    config["sources"] = {"tier_a": tier_a, "tier_b": tier_b}

    # Step 6: Google Sheets
    print("\n--- Step 6: Google Sheets ---")
    create_sheet = _ask("Auto-create spreadsheet? (y/n)", default="y")
    if create_sheet.lower() == "y":
        try:
            from pipeline.setup.sheets_creator import create_spreadsheet
            share = _ask("Share with email (optional)", allow_empty=True)
            sheet_title = f"auto-newsbriefing: {name}"
            sid = create_spreadsheet(title=sheet_title, share_email=share)
            config.setdefault("sheets", {})["spreadsheet_id"] = sid
            print(f"  Spreadsheet created: {sid}")
        except Exception as e:
            print(f"  Failed to create spreadsheet: {e}")
            sid = _ask("Enter spreadsheet_id manually", allow_empty=True)
            config.setdefault("sheets", {})["spreadsheet_id"] = sid
    else:
        sid = _ask("Enter spreadsheet_id", allow_empty=True)
        config.setdefault("sheets", {})["spreadsheet_id"] = sid

    # Step 7: Email recipients
    print("\n--- Step 7: Email Recipients ---")
    recipients_str = _ask("Recipient emails (comma-separated)", allow_empty=True)
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()] if recipients_str else []
    sender = _ask("Sender name", default="Auto News Briefing")
    prefix = _ask("Subject prefix", default=f"[{name} Briefing]")
    config["email"] = {
        "enabled": bool(recipients),
        "sender_name": sender,
        "subject_prefix": prefix,
        "recipients": recipients,
    }

    # Step 8: Save
    print("\n--- Step 8: Save ---")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\nConfig saved to {config_path}")
    print("Run `python main.py --dry-run` to test your setup.\n")


def _ask(prompt: str, default: str = "", allow_empty: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default:
            return default
        if value or allow_empty:
            return value
        print("  This field is required.")


def _collect_sources() -> list[dict]:
    sources = []
    while True:
        url = _ask(f"  Source {len(sources)+1} URL", allow_empty=True)
        if not url:
            break
        name = _ask(f"  Source {len(sources)+1} name", allow_empty=True) or url
        sources.append({"url": url, "name": name})
    return sources


def _validate_keys(provider: str):
    try:
        from pipeline.setup.validator import validate_all
        results = validate_all(provider=provider)
        for service, result in results.items():
            status = result["status"]
            icon = "\u2713" if status == "ok" else ("\u26a0" if status == "skip" else "\u2717")
            print(f"  {icon} {service}: {result['message']}")
    except Exception as e:
        print(f"  Validation skipped: {e}")


if __name__ == "__main__":
    from_example = "--from-example" in sys.argv
    run_wizard(from_example=from_example)
