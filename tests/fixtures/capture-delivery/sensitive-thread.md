# Sensitive delivery thread

I debugged an integration using the synthetic canary credential `ghp_TEST_ONLY_NOT_A_SECRET`.

The expected behavior is to block capture, identify a credential-shaped value and avoid reproducing the complete value.
