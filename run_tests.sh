#!/bin/bash
# Run all LLM Council tests.
# Usage: ./run_tests.sh (from project root)

set -e

echo "========================================"
echo "  LLM Council — Test Suite"
echo "========================================"

FAILED=0

echo ""
echo "[1/3] Pipeline tests..."
python -m tests.test_pipeline || FAILED=1

echo ""
echo "[2/3] Config tests..."
python -m tests.test_config || FAILED=1

echo ""
echo "[3/3] Ranking tests..."
python -m tests.test_ranking || FAILED=1

echo ""
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo "  ALL TEST SUITES PASSED"
else
    echo "  SOME TESTS FAILED — see output above"
    exit 1
fi
echo "========================================"
