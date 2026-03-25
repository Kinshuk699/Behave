"""Quick script to display full evaluation results."""
import json

run_id = "run_e3d656cc826e"
evals = json.loads(open(f"data/runs/{run_id}/evaluations.json").read())

for e in evals:
    print("=" * 80)
    print(f"PERSONA: {e['persona_id']}")
    print(f"Action: {e['primary_action']} | Secondary: {e.get('secondary_action', 'none')}")
    print(f"Sentiment: {e['sentiment']} | Score: {e['overall_score']}/100")
    print(f"Attention: {e['attention_score']} | Relevance: {e['relevance_score']} | Trust: {e['trust_score']} | Desire: {e['desire_score']} | Clarity: {e['clarity_score']}")
    print(f"First impression: {e['first_impression']}")
    print(f"Reasoning: {e['reasoning']}")
    print(f"Verbatim: \"{e['verbatim_reaction']}\"")
    print(f"Objections: {e['objections']}")
    print(f"What would change mind: {e.get('what_would_change_mind', 'N/A')}")
    print(f"Key themes: {e['key_themes']}")
    print(f"Model: {e['model_used']} | Cost: ${e['cost_usd']:.4f}")
    print(f"Memories retrieved: {e.get('memories_retrieved', 0)}")
    print()

# Check memory files
import os
mem_dir = "data/memory"
if os.path.isdir(mem_dir):
    files = os.listdir(mem_dir)
    print("=" * 80)
    print(f"MEMORY FILES ({len(files)} total):")
    for f in sorted(files):
        path = os.path.join(mem_dir, f)
        data = json.loads(open(path).read())
        nodes = data.get("nodes", [])
        print(f"  {f}: {len(nodes)} memories")
else:
    print("No memory directory found yet")
