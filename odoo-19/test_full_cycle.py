import sys
sys.path.insert(0, '/Users/tri-mac/Obsidian Vault/Odoo 19')

def test_full_research_cycle():
    """Test complete research cycle on stock.quant model."""
    from research_agent import ResearchAgent

    # 1. Initialize
    agent = ResearchAgent()

    # 2. Research one model
    results = agent.research_model('stock', 'stock.quant')

    # 3. Verify results
    assert results['verification']['verified'] == True, "Model should be verified"
    assert len(results['depth']['fields']) > 0, "Should find fields"
    assert len(results['depth']['methods']) > 0, "Should find methods"

    # 4. Check documentation generated
    doc = results['documentation']
    assert 'stock.quant' in doc, "Documentation should mention model name"
    assert 'verification_status' in doc, "Should have verification status"
    assert 'quantity' in doc, "Should mention quantity field"

    # 5. Check depth levels
    quantity_field = next((f for f in results['depth']['fields'] if f['name'] == 'quantity'), None)
    assert quantity_field is not None, "Should find quantity field"
    assert 'level_1' in quantity_field['depth'], "Should have level 1 depth"

    print(f"Full cycle test passed!")
    print(f"  Verified fields: {len(results['depth']['fields'])}")
    print(f"  Verified methods: {len(results['depth']['methods'])}")
    print(f"  Documentation length: {len(doc)} chars")

if __name__ == "__main__":
    test_full_research_cycle()
