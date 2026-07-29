Use the `capture-delivery` skill on this thread:

I led an improvement to a synthetic CI pipeline used by six engineers. Builds took 20 minutes and delayed feedback. I profiled the stages, split independent suites and introduced bounded parallel execution. Median duration fell from 20 to 12 minutes over the following two weeks, with no increase in flaky-test retries.

Return the reviewable delivery draft.
