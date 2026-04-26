"""
Teste local do fluxo Marketing Agent:
  1. Claude Sonnet gera caption + hashtags
  2. Replicate Flux Schnell gera imagem
  3. Imprime o preview completo (sem publicar no Instagram)

Uso:
  python scripts/test_marketing_post.py "spring cleanup"
  python scripts/test_marketing_post.py "lawn care tips" roberts
  python scripts/test_marketing_post.py "AI marina management" dockplusai
"""
import asyncio
import sys

sys.path.insert(0, ".")


async def main() -> None:
    from maestro.agents.marketing import MarketingAgent
    from maestro.config import get_settings
    from maestro.profiles import load_profile

    topic = sys.argv[1] if len(sys.argv) > 1 else "spring cleanup tips"
    business = sys.argv[2] if len(sys.argv) > 2 else "roberts"

    settings = get_settings()
    profile = load_profile(business)
    agent = MarketingAgent(settings, profile)

    print(f"\n=== Marketing Agent — '{topic}' ({business}) ===\n")
    print("Gerando caption + imagem...\n")

    result, run = await agent.create_post(topic)
    preview = result.approval.preview if result.approval else result.data

    print(f"Caption:\n{preview.get('caption')}\n")
    print(f"Hashtags: {' '.join(preview.get('hashtags', []))}\n")
    print(f"Visual prompts: {preview.get('visual_prompts')}\n")
    image_url = preview.get("image_url", "")
    if image_url:
        print(f"Imagem gerada: {image_url}\n")
    else:
        print("Imagem: não gerada (token ausente ou erro)\n")
    print(f"Agendado para: {preview.get('scheduled_at')}")
    print(f"Dry run: {preview.get('dry_run')}")
    print(f"Rationale: {preview.get('rationale', '—')}")
    print(f"\nApproval ID: {result.approval.id if result.approval else '—'}")


asyncio.run(main())
