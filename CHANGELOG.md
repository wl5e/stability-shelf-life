# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Backlog items planned for the next stability-analysis release.

## [2.0.0] - 2025-01-01

### Added
- ICH Q1E shelf-life estimation with one-sided 95% lower confidence bounds.
- Zero-order and first-order kinetics with automatic best-model selection.
- Per-batch analysis, slope-difference F tests, and optional batch pooling.
- Multiple specification limits in a single `q1e` run.
- BCa bootstrap lower bounds and confidence-band plotting.
- Arrhenius extrapolation with activation energy and shelf-life prediction.
- JSON, standalone HTML, and ICH Q1A/Q1E summary-table reports.
- Optional `batch_id` support for accelerated-stability input.

### Changed
- Input loaders detect comma, semicolon, and tab delimiters.
- Reports include explicit units for time, potency, and temperature.

### Fixed
- Reject non-finite, negative-time, and non-positive-potency input early.

## [1.0.0] - 2024-01-01

### Added
- Initial kinetics, shelf-life estimation, and Arrhenius extrapolation tools.
- Standard-library-only packaging and console entry point.

## [Unreleased]: https://github.com/wl5e/stability-shelf-life/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/wl5e/stability-shelf-life/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/wl5e/stability-shelf-life/releases/tag/v1.0.0
