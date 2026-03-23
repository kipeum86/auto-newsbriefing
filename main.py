"""auto-newsbriefing — domain-agnostic RSS newsletter automation."""

import argparse
import logging
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from pipeline.config import (
    DEFAULT_CONFIG_PATH,
    get_config_with_defaults,
    load_config,
    setup_logging,
    validate_config,
)

load_dotenv()

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="auto-newsbriefing")
    parser.add_argument("--dry-run", action="store_true", help="Skip Sheets upload and email")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls")
    parser.add_argument("--max-items", type=int, default=0, help="Limit articles processed")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config file path")
    return parser.parse_args()


def main():
    args = parse_args()

    # Load & validate config
    raw_config = load_config(args.config)
    if not validate_config(raw_config):
        print("Run `python -m pipeline.setup.wizard` to configure.")
        sys.exit(1)
    config = get_config_with_defaults(raw_config)
    setup_logging(config)

    domain = config["domain"]
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    llm = None  # initialized lazily when needed
    logger.info("=== auto-newsbriefing: %s (%s) ===", domain["description"], run_date)

    # [1/6] Collect RSS
    from pipeline.collector import collect_articles, extract_body
    articles, failed = collect_articles(config)
    if not articles:
        logger.warning("No articles collected. Exiting.")
        return
    logger.info("[1/6] Collected %d articles (%d sources failed)", len(articles), len(failed))

    # [2/6] Pre-LLM dedup
    from pipeline.dedup import (
        deduplicate_articles,
        deduplicate_by_event_key,
        load_trend_snapshot,
        save_trend_file,
    )
    from pipeline.models import DedupSnapshot

    trends_dir = str(__import__("pathlib").Path(__file__).parent / "trends")
    trend_snapshot = load_trend_snapshot(trends_dir)

    if not args.dry_run:
        from pipeline.archiver import load_sheets_snapshot
        sheets_snapshot = load_sheets_snapshot(config.get("sheets", {}).get("spreadsheet_id", ""))
        # Merge snapshots
        trend_snapshot.urls |= sheets_snapshot.urls
        trend_snapshot.canonical_urls |= sheets_snapshot.canonical_urls
        trend_snapshot.topic_token_sets.extend(sheets_snapshot.topic_token_sets)
        trend_snapshot.event_keys |= sheets_snapshot.event_keys

    dedup_config = config.get("collection", {}).get("dedup", {})
    articles = deduplicate_articles(articles, trend_snapshot, dedup_config)
    logger.info("[2/6] After dedup: %d articles", len(articles))

    # [3/6] Keyword filter + Top-N selection
    from pipeline.classifier import (
        is_usable_result,
        keyword_filter,
        select_top_articles,
        summarize_article,
    )

    articles = keyword_filter(articles, config.get("keywords", {}))

    if not args.no_llm and not args.max_items:
        from pipeline.llm import create_provider
        llm = create_provider(
            config["llm"]["provider"],
            config["llm"].get("model", ""),
        )
        articles = select_top_articles(articles, llm, config)
    elif args.max_items:
        articles = articles[: args.max_items]
    else:
        top_n = config.get("collection", {}).get("top_n", 10)
        articles = articles[:top_n]

    logger.info("[3/6] After selection: %d articles", len(articles))

    # [4/6] Body extraction + Summarization
    min_len = config.get("collection", {}).get("min_content_length", 200)
    for article in articles:
        body = extract_body(article.url, min_len)
        article.body = body or article.description

    processed = []
    if not args.no_llm:
        if llm is None:
            from pipeline.llm import create_provider
            llm = create_provider(config["llm"]["provider"], config["llm"].get("model", ""))
        for article in articles:
            pa = summarize_article(article, llm, config)
            processed.append(pa)
        # Filter low-confidence
        processed = [pa for pa in processed if is_usable_result(pa.ai_result)]
    else:
        from pipeline.models import AIResult, ProcessedArticle
        default_cat = config.get("categories", [{}])[-1].get("name", "ETC") if config.get("categories") else "ETC"
        for article in articles:
            pa = ProcessedArticle(
                article=article,
                ai_result=AIResult(summary=[article.title], category=default_cat, confidence="low"),
            )
            processed.append(pa)

    logger.info("[4/6] Summarized %d articles", len(processed))

    # [5/6] Post-summary dedup (EventKey)
    if dedup_config.get("event_key_enabled", True) and not args.no_llm:
        processed = deduplicate_by_event_key(processed)
    primary = [pa for pa in processed if pa.ai_result.is_primary]
    logger.info("[5/6] After EventKey dedup: %d primary articles", len(primary))

    if not primary:
        logger.info("No primary articles to report. Done.")
        return

    # [6/6] Output
    if not args.dry_run:
        # Google Sheets
        from pipeline.archiver import upload_to_sheets
        upload_to_sheets(processed, config.get("sheets", {}).get("spreadsheet_id", ""), run_date)

        # Email
        from pipeline.mailer import build_html_email, send_email
        if config.get("email", {}).get("enabled", True):
            html = build_html_email(processed, config, run_date)
            send_email(html, config, run_date)

    # Trend archive
    save_trend_file(trends_dir, processed, run_date)
    logger.info("[6/6] Done. %d primary articles briefed.", len(primary))

    # Dry-run summary
    if args.dry_run:
        print(f"\n--- DRY RUN SUMMARY ({run_date}) ---")
        for pa in primary:
            print(f"\n[{pa.ai_result.category}] {pa.article.title}")
            print(f"  Source: {pa.article.source}")
            for s in pa.ai_result.summary:
                print(f"  - {s}")


if __name__ == "__main__":
    main()
