import concurrent.futures
import time
import json
from datetime import datetime

from verification_engine import VerificationEngine
from depth_engine import DepthEscalationEngine

class ResearchAgent:
    """Main research agent that runs verification + depth in parallel."""

    def __init__(self, addons_path=None):
        self.ve = VerificationEngine(addons_path)
        self.de = DepthEscalationEngine(self.ve)
        self.checkpoint_interval = 600  # 10 minutes
        self.last_checkpoint = time.time()

    def research_model(self, module, model_name):
        """Research a model with parallel verification + depth."""
        results = {
            'module': module,
            'model': model_name,
            'verification': None,
            'depth': None,
            'documentation': None
        }

        # Run verification and depth in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            ver_future = executor.submit(self.ve.verify_model, module, model_name)
            depth_future = executor.submit(self._depth_explore_model, module, model_name)

            results['verification'] = ver_future.result()
            results['depth'] = depth_future.result()

        # Generate documentation from results
        results['documentation'] = self._generate_doc(results)

        return results

    def _depth_explore_model(self, module, model_name):
        """Explore depth for all fields and methods in model."""
        depth_result = {
            'fields': [],
            'methods': []
        }

        # Get model info
        model_info = self.ve.verify_model(module, model_name)
        if not model_info['verified']:
            return depth_result

        # For each field, run depth escalation
        for field in model_info['fields']:
            field_depth = self.de.escalate_field(module, model_name, field['name'])
            depth_result['fields'].append({
                'name': field['name'],
                'depth': field_depth
            })

        # For each method, run depth escalation
        for method in model_info['methods']:
            method_depth = self.de.escalate_method(module, model_name, method['name'])
            depth_result['methods'].append({
                'name': method['name'],
                'depth': method_depth
            })

        return depth_result

    def _generate_doc(self, results):
        """Generate documentation markdown from verification + depth results."""
        verification = results['verification']
        depth = results['depth']

        doc = f"""---
type: model
module: {results['module']}
model: {results['model']}
verification_status: {"verified" if verification['verified'] else "unverified"}
verified_at: {datetime.now().strftime('%Y-%m-%d')}
confidence: {verification.get('confidence', 'unknown')}
source: {verification.get('source_file', 'Unknown')}
---

# {results['model']}

## Verification

**Status:** {"Verified" if verification['verified'] else "Not Verified"}
**Source:** {verification.get('source_file', 'Unknown')}
**Line:** {verification.get('line_number', 'Unknown')}

## Fields

"""
        # Add fields with depth
        for field in depth.get('fields', []):
            doc += f"### {field['name']}\n\n"
            doc += f"- **L1 (Surface):** {field['depth']['level_1'].get('definition', 'N/A')}\n"
            doc += f"- **L2 (Context):** {field['depth']['level_2'].get('purpose', 'Unknown')}\n"

            l3_questions = field['depth']['level_3'].get('edge_values', [])
            if l3_questions:
                doc += "- **L3 (Edge Cases):**\n"
                for q in l3_questions:
                    doc += f"  - {q}\n"

            doc += "\n"

        doc += "## Methods\n\n"
        for method in depth.get('methods', []):
            doc += f"### {method['name']}\n\n"
            l1 = method['depth']['level_1']
            l2 = method['depth']['level_2']
            l3 = method['depth']['level_3']

            doc += f"- **Signature:** {l1.get('signature', 'Unknown')}\n"
            doc += f"- **Purpose:** {l2.get('purpose', 'Unknown')}\n"
            doc += f"- **Callers:** {len(l2.get('callers', []))} found\n"
            doc += f"- **Callees:** {len(l2.get('callees', []))} found\n"

            if l3.get('concurrency', {}).get('has_lock') == False:
                doc += f"- **Concurrency:** {l3['concurrency']['note']}\n"
            if l3.get('security', {}).get('uses_sudo'):
                doc += "- **Security:** Uses sudo() - ACL bypass possible\n"

            doc += "\n"

        return doc

    def should_checkpoint(self):
        """Check if it's time to save a checkpoint."""
        now = time.time()
        if now - self.last_checkpoint >= self.checkpoint_interval:
            self.last_checkpoint = now
            return True
        return False


def test_research_agent():
    """Test the research agent on stock.quant model."""
    agent = ResearchAgent()

    print("=" * 70)
    print("RESEARCH AGENT TEST - stock.quant")
    print("=" * 70)

    # Run research
    results = agent.research_model('stock', 'stock.quant')

    # Print summary
    print(f"\nModule: {results['module']}")
    print(f"Model: {results['model']}")
    print(f"Verified: {results['verification']['verified']}")
    print(f"Source: {results['verification'].get('source_file', 'Unknown')}")
    print(f"Confidence: {results['verification'].get('confidence', 'unknown')}")

    print(f"\nFields found: {len(results['depth'].get('fields', []))}")
    print(f"Methods found: {len(results['depth'].get('methods', []))}")

    # Show first 5 fields
    print("\n--- Sample Fields (first 5) ---")
    for field in results['depth'].get('fields', [])[:5]:
        print(f"  {field['name']}: {field['depth']['level_2'].get('purpose', 'Unknown')}")

    # Show first 5 methods
    print("\n--- Sample Methods (first 5) ---")
    for method in results['depth'].get('methods', [])[:5]:
        print(f"  {method['name']}: {method['depth']['level_2'].get('purpose', 'Unknown')}")

    # Print documentation
    print("\n--- Generated Documentation ---")
    print(results['documentation'][:2000])  # First 2000 chars

    return results


if __name__ == '__main__':
    test_research_agent()
