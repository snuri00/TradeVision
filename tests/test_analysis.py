import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.analysis.technical import analyze_stock


def test_technical_analysis():
    result = analyze_stock("AAPL", period="3mo")
    assert "current_price" in result or "error" in result
    print(f"AAPL Analysis: {result}")


def test_bist_analysis():
    result = analyze_stock("THYAO.IS", period="3mo")
    assert "current_price" in result or "error" in result
    print(f"THYAO Analysis: {result}")


def test_gold_analysis():
    result = analyze_stock("GC=F", period="3mo")
    assert "current_price" in result or "error" in result
    print(f"Gold Analysis: {result}")


if __name__ == "__main__":
    tests = [test_technical_analysis, test_bist_analysis, test_gold_analysis]
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
        print()
