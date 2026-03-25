from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from .agent import CommerceAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Commerce agent with chat and multimodal search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat = subparsers.add_parser("chat", help="Chat with the commerce agent")
    chat.add_argument("prompt")
    chat.add_argument("--image")

    text_search = subparsers.add_parser("text-search", help="Search by text query")
    text_search.add_argument("query", nargs="?", default="")
    text_search.add_argument("--category")
    text_search.add_argument("--limit", type=int, default=5)

    image_search = subparsers.add_parser("image-search", help="Search with a real image file")
    image_search.add_argument("image_path")
    image_search.add_argument("--limit", type=int, default=5)

    multimodal = subparsers.add_parser("multimodal-search", help="Combine text and image intent")
    multimodal.add_argument("--text", default="")
    multimodal.add_argument("--image")
    multimodal.add_argument("--category")
    multimodal.add_argument("--limit", type=int, default=5)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    agent = CommerceAgent()
    try:
        if args.command == "chat":
            print(agent.chat(args.prompt, image_path=args.image))
            return

        if args.command == "text-search":
            products = agent.text_search(
                args.query,
                category=args.category,
                limit=args.limit,
            )
            print(json.dumps([asdict(product) for product in products], indent=2))
            return

        if args.command == "image-search":
            analysis, products = agent.image_search(args.image_path, limit=args.limit)
            print(
                json.dumps(
                    {
                        "analysis": asdict(analysis),
                        "matches": [asdict(product) for product in products],
                    },
                    indent=2,
                    default=str,
                )
            )
            return

        if args.command == "multimodal-search":
            if not args.text and not args.image:
                raise ValueError("multimodal-search requires --text, --image, or both")
            analysis, products = agent.multimodal_search(
                text_query=args.text,
                image_path=args.image,
                category=args.category,
                limit=args.limit,
            )
            print(
                json.dumps(
                    {
                        "analysis": asdict(analysis) if analysis else None,
                        "matches": [asdict(product) for product in products],
                    },
                    indent=2,
                    default=str,
                )
            )
    except (ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
