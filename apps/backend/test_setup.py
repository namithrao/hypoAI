"""
Test script to verify Claude API and BlueBERT setup.

Run this after: pip install -r requirements.txt
"""

import os
import sys


def test_imports():
    """Test that all required packages are installed."""
    print("Testing imports...")

    try:
        import torch
        print(f"✓ PyTorch {torch.__version__}")
    except ImportError as e:
        print(f"✗ PyTorch not installed: {e}")
        return False

    try:
        import transformers
        print(f"✓ Transformers {transformers.__version__}")
    except ImportError as e:
        print(f"✗ Transformers not installed: {e}")
        return False

    try:
        import anthropic
        print(f"✓ Anthropic {anthropic.__version__}")
    except ImportError as e:
        print(f"✗ Anthropic not installed: {e}")
        return False

    return True


def test_claude_api():
    """Test Claude API connection."""
    print("\nTesting Claude API...")

    try:
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠ ANTHROPIC_API_KEY not set in environment")
            print("  Set it with: export ANTHROPIC_API_KEY='your-key-here'")
            return False

        client = Anthropic(api_key=api_key)

        # Simple test message
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'API working' if you can read this."}]
        )

        response_text = message.content[0].text
        print(f"✓ Claude API connected: {response_text[:50]}")
        return True

    except Exception as e:
        print(f"✗ Claude API error: {e}")
        return False


def test_bluebert():
    """Test BlueBERT model loading."""
    print("\nTesting BlueBERT...")

    try:
        from transformers import AutoTokenizer, AutoModel
        import torch

        print("  Downloading BlueBERT (first time only, ~420MB)...")

        # Load BlueBERT-Base
        model_name = "bionlp/bluebert_pubmed_mimic_uncased_L-12_H-768_A-12"

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)

        print(f"✓ BlueBERT loaded: {model_name}")

        # Test inference
        test_text = "The patient has elevated C-reactive protein (CRP) levels."
        inputs = tokenizer(test_text, return_tensors="pt")

        with torch.no_grad():
            outputs = model(**inputs)

        embeddings = outputs.last_hidden_state
        print(f"✓ BlueBERT inference test passed")
        print(f"  Input: '{test_text}'")
        print(f"  Output shape: {embeddings.shape}")

        return True

    except Exception as e:
        print(f"✗ BlueBERT error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("SynthAI Setup Verification")
    print("=" * 60)

    results = []

    # Test imports
    results.append(("Imports", test_imports()))

    # Test Claude API
    results.append(("Claude API", test_claude_api()))

    # Test BlueBERT
    results.append(("BlueBERT", test_bluebert()))

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 All tests passed! Setup is complete.")
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
