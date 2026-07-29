### Reduced CI feedback time

- Situation: CI feedback took 20 minutes for six engineers.
- Task: Improve feedback speed without increasing flaky retries.
- Action: I profiled the suites and introduced bounded parallel execution.
- Result: Median duration fell from 20 to 12 minutes, a 40% reduction, with no increase in flaky retries.
- Evidence: 20 minutes, 12 minutes, six engineers, no increase in flaky retries.
- Confidence: complete
