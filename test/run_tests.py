"""
Kioxus Test Runner

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --quick            # Quick smoke test
    python run_tests.py --verbose          # Verbose output
"""

import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

# Test files in order
TESTS = [
    'tests/test_core_smoke.py',
    'tests/test_phase2_smoke.py',
    'tests/test_phase3_smoke.py',
    'tests/test_verifier.py',
    'tests/test_sandbox.py',
    'tests/test_context_budget.py',
    'tests/test_memory.py',
]

QUICK_TESTS = [
    'tests/test_core_smoke.py',
    'tests/test_verifier.py',
]


def run_test(test_file, verbose=False):
    """Run a single test file."""
    print(f'\n{"="*60}')
    print(f'Test: {test_file}')
    print(f'{"="*60}')

    start = time.time()

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)) or '.'
        )

        if result.returncode == 0:
            print(f'PASS: {test_file}')
            passed = True
        else:
            print(f'FAIL: {test_file}')
            if verbose:
                print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
            passed = False

    except Exception as e:
        print(f'ERROR: {test_file} - {e}')
        passed = False

    elapsed = time.time() - start
    print(f'Time: {elapsed:.2f}s')

    return passed, elapsed


def main():
    """Run all tests."""
    verbose = '--verbose' in sys.argv
    quick = '--quick' in sys.argv

    test_list = QUICK_TESTS if quick else TESTS

    print(f'Kioxus Test Runner')
    print(f'Tests: {len(test_list)}')
    print(f'Mode: {"quick" if quick else "full"}')

    results = []
    total_time = 0

    for test in test_list:
        passed, elapsed = run_test(test, verbose)
        results.append((test, passed))
        total_time += elapsed

    # Summary
    print(f'\n{"="*60}')
    print(f'Test Summary')
    print(f'{"="*60}')

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    for test, passed in results:
        status = 'PASS' if passed else 'FAIL'
        print(f'  [{status}] {test}')

    print(f'\nTotal: {passed_count}/{total_count} passed')
    print(f'Total time: {total_time:.2f}s')

    if passed_count == total_count:
        print('\nAll tests passed!')
        return 0
    else:
        print(f'\n{total_count - passed_count} test(s) failed!')
        return 1


if __name__ == '__main__':
    sys.exit(main())
