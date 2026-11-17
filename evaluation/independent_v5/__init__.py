"""Offline tooling for the v5 independent evaluation of hybrid v3 (evaluation/independent_test_protocol_v5.md).

Import boundaries (checked by tests/test_independent_v5.py):
  config, stats, labels, scorer, exclusion, datecheck   standard library and each other only; never `app`
  validator                                              reads production chunking and the keyword lexicons (read-only)
  retrieval, transport, pipeline, runner                 run the frozen implementation read-only

Nothing here makes a network request unless runner.execute is given an explicit written authorisation, the
approval environment variable and a key; tests only ever pass fake transports.
"""
