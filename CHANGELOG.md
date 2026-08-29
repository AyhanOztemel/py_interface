# Changelog

All notable changes to this project are documented here.

## 0.4.0 - 2026-08-30

### Added

- New `interface_contract` import package and `interface-contract` distribution
  name.
- Opt-in instance-field contracts through `check_attributes=True`.
- `AttributeSpec`, `attributes_of`, `missing_attributes`, `verify_instance`, and
  `satisfies` inspection and validation APIs.
- Explicit adapter registries and process-wide adapter helpers.
- Optional mypy plugin for detecting incomplete implementations statically.
- English primary documentation and a Turkish companion guide.
- Dataclass compatibility coverage.

### Compatibility

- `strict_interface` remains a supported alias with identical public objects.
- Existing annotation behavior is unchanged unless field checking is explicitly
  enabled.

## 0.3.0

- Added Python 3.14 support and fail-closed bytecode stub detection.
- Improved custom metaclass composition.

## 0.2.0

- Made interface validation automatic at class-definition time.
- Added `abstract=True` for intentionally incomplete intermediate classes.
