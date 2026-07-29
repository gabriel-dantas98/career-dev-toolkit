I led an improvement to a synthetic CI pipeline used by six engineers. Builds took 20 minutes and delayed feedback.

I profiled the test stages, split independent suites and introduced bounded parallel execution. I documented the rollback path.

Over the following two weeks, median duration fell from 20 minutes to 12 minutes with no increase in flaky-test retries.
