# Q028/WDBC flagship canonical reproduction notes

## Scope

Controlled binary classification exercise (UCI WDBC). Demonstrates the AI Scientist plan-execute-review-revise workflow. Not a cure, not a clinical validation, not medical advice, not generalizable to other cancers.

## Round 1 -> Round 2

Target metric: `malignant_recall` >= 0.95.

| metric | round1 | round2 | delta |
| --- | --- | --- | --- |
| balanced_accuracy | 0.9642857142857143 | 0.9761904761904762 | 0.011904761904761862 |
| false_negative_rate | None | 0.04761904761904767 | None |
| malignant_recall | 0.9285714285714286 | 0.9523809523809523 | 0.023809523809523725 |

## Round 2 execution reproduction report

# Round 2 reproduction report

This package records a paired internal sensitivity analysis. It is not independent external validation and is not for clinical use. A second clean-environment package must be compared before scientific reproduction is claimed.
