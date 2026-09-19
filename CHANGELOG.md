# Changelog

## [0.3.0](https://github.com/andrewkriley/theshed/compare/theshed-v0.2.0...theshed-v0.3.0) (2026-09-19)


### Features

* approval-gate resume (POST /turns/{id}/approvals) ([d97a212](https://github.com/andrewkriley/theshed/commit/d97a212cc41a4ad4b72467c00707c3ca249e6985))
* full-detail Galileo tracing (llm spans, session-per-conversation) ([35bb484](https://github.com/andrewkriley/theshed/commit/35bb4847c51ba7dd55aa6d6f66c3b1f15a02d541))


### Bug Fixes

* actually flush Galileo traces (session existed, spans never did) ([984ecd8](https://github.com/andrewkriley/theshed/commit/984ecd8fd5a942bcd93cb99d8720e697f1366ff3))
* point Galileo at the actual console, not the public default ([a081ccc](https://github.com/andrewkriley/theshed/commit/a081ccc5098c0d02d15e98f0f1be65a9c2865a1b))
* spans were never nesting under their trace (invalid agent_type) ([b399205](https://github.com/andrewkriley/theshed/commit/b39920565cc0a5bfe1af3562180bbaf3547ec4cd))

## [0.2.0](https://github.com/andrewkriley/theshed/compare/theshed-v0.1.0...theshed-v0.2.0) (2026-09-18)


### Features

* give assist the code_execution tool alongside web_search ([ca07276](https://github.com/andrewkriley/theshed/commit/ca07276efc720aa3f317027ae2b6d6dd24bdeb6f))
* manual turn verifier and provider/model settings surface ([eec2e7c](https://github.com/andrewkriley/theshed/commit/eec2e7c3f8fa687e87530ff202a3209fade1ba72))
