# Changelog

## [0.4.5](https://github.com/andrewkriley/shedlife.ai/compare/theshed-v0.4.4...theshed-v0.4.5) (2026-09-19)


### Bug Fixes

* name the bootstrap CT theshed-deploy and add --delete ([#18](https://github.com/andrewkriley/shedlife.ai/issues/18)) ([189b2c6](https://github.com/andrewkriley/shedlife.ai/commit/189b2c61ea79d097c702219d6816a2f10e39b8fb))

## [0.4.4](https://github.com/andrewkriley/shedlife.ai/compare/theshed-v0.4.3...theshed-v0.4.4) (2026-09-19)


### Bug Fixes

* print the Shed ASCII banner at the start of install.sh ([fe112ac](https://github.com/andrewkriley/shedlife.ai/commit/fe112ac001baea185498861f9f2a5e84f14d2e74))
* skip a missing local-lvm instead of aborting install ([2319e1c](https://github.com/andrewkriley/shedlife.ai/commit/2319e1c5efbbd2e6acec68c3e8cb9ad27a021e10))

## [0.4.3](https://github.com/andrewkriley/shedlife.ai/compare/theshed-v0.4.2...theshed-v0.4.3) (2026-09-19)


### Bug Fixes

* pick a rootdir storage instead of assuming local-lvm ([28b7de1](https://github.com/andrewkriley/shedlife.ai/commit/28b7de1f35b053c37448f32f4845c9f333bd4bc8))
* pin the bootstrap CT to Ubuntu 26.04 ([db99fbe](https://github.com/andrewkriley/shedlife.ai/commit/db99fbe216871e98f038e8eeed309240b9dad813))

## [0.4.2](https://github.com/andrewkriley/shedlife.ai/compare/theshed-v0.4.1...theshed-v0.4.2) (2026-09-19)


### Bug Fixes

* attach install.sh from the release-please job ([760f08a](https://github.com/andrewkriley/shedlife.ai/commit/760f08ae5dbe1ad5c743951e3d4dd036f8fc4a33))
* create the bootstrap CT from the latest Ubuntu template ([a73a469](https://github.com/andrewkriley/shedlife.ai/commit/a73a469366a27ad66b3392c1e67370cf2661e2d9))

## [0.4.1](https://github.com/andrewkriley/shedlife.ai/compare/theshed-v0.4.0...theshed-v0.4.1) (2026-09-19)


### Bug Fixes

* one-line install from the latest release asset ([95de117](https://github.com/andrewkriley/shedlife.ai/commit/95de1172b50dde903c08c798e5530cb9392b2343))

## [0.4.0](https://github.com/andrewkriley/shedlife.ai/compare/theshed-v0.3.0...theshed-v0.4.0) (2026-09-19)


### Features

* bootstrap Phase 1 profile, setup gate, and installer ([e6d79f0](https://github.com/andrewkriley/shedlife.ai/commit/e6d79f0553c72d0b9acb7b6e258e0d07b71b4383))

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
