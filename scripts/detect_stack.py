#!/usr/bin/env python3
"""
detect_stack.py - mechanical stack detection for the flutter-sdlc-pipeline plugin.

WHAT IT IS FOR
--------------
The orchestrator must not read project files to learn the stack - every read is a context
re-send. This script reads them instead and prints a small block the orchestrator pastes,
unread, into the plan's Global Constraints. Implementers receive Global Constraints inline,
so every downstream agent gets the exact toolchain commands without opening pubspec.yaml.

USAGE
-----
    python3 detect_stack.py [repo-root]

First line is always `STACK: flutter | dart | generic`. For `generic` nothing else is printed
and the pipeline behaves exactly as it did before stack profiles existed.

Exit 0 always. Detection is best-effort; a missing signal prints `none detected`, never a guess.

DESIGN RULES
------------
1. Report what the repo says, never what it should say. No recommendations in the output.
2. A signal that cannot be read stays silent.
3. Output must stay under ~30 lines - it is pasted into every implementer dispatch.
"""

import os
import re
import sys

STATE_MGMT = ["flutter_riverpod", "hooks_riverpod", "riverpod", "flutter_bloc", "bloc",
              "provider", "get", "mobx", "signals", "stacked"]
ROUTING = ["go_router", "auto_route", "beamer", "routemaster", "fluro"]
GENERATORS = ["freezed", "json_serializable", "riverpod_generator", "drift_dev",
              "injectable_generator", "auto_route_generator", "hive_generator", "isar_generator",
              "retrofit_generator", "mockito", "built_value_generator", "envied_generator",
              "flutter_gen_runner", "objectbox_generator"]
STORAGE = ["drift", "sqflite", "hive", "hive_ce", "isar", "objectbox", "shared_preferences",
           "flutter_secure_storage", "firebase_database", "cloud_firestore"]
TEST_LIBS = ["mocktail", "mockito", "bloc_test", "golden_toolkit", "alchemist", "patrol",
             "network_image_mock", "fake_async"]
LINTS = ["very_good_analysis", "flutter_lints", "lints", "lint", "pedantic"]
PLATFORMS = ["android", "ios", "web", "macos", "linux", "windows"]

# Codegen outputs. Mirrored in the Stage 5 review-diff filter in commands/pipeline*.md.
GENERATED_GLOBS = ["*.g.dart", "*.freezed.dart", "*.gr.dart", "*.mocks.dart",
                   "*.config.dart", "app_localizations*.dart"]


def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def deps_of(pubspec):
    """Top-level package names under dependencies / dev_dependencies (2-space indent)."""
    names, in_deps = set(), False
    for line in pubspec.splitlines():
        if re.match(r"^(dependencies|dev_dependencies|dependency_overrides):", line):
            in_deps = True
            continue
        if re.match(r"^\S", line):
            in_deps = False
        if in_deps and (m := re.match(r"^  ([a-z_][a-z0-9_]*):", line)):
            names.add(m.group(1))
    return names


def pick(names, wanted):
    return [w for w in wanted if w in names]


def flavors(root):
    found = set()
    for g in ("android/app/build.gradle", "android/app/build.gradle.kts"):
        txt = read(os.path.join(root, g))
        if m := re.search(r"productFlavors\s*\{(.*?)\n\s{4}\}", txt, re.S):
            found |= set(re.findall(r"^\s*(?:create\(\")?(\w+)\"?\)?\s*\{", m.group(1), re.M))
    lib = os.path.join(root, "lib")
    if os.path.isdir(lib):
        found |= {f[5:-5] for f in os.listdir(lib) if re.match(r"main_\w+\.dart$", f)}
    return sorted(found)


def has_goldens(root):
    test = os.path.join(root, "test")
    base = test.count(os.sep)
    for dirpath, dirnames, _ in os.walk(test):
        if "goldens" in dirnames:
            return True
        if dirpath.count(os.sep) - base > 4:
            dirnames[:] = []
    return False


def generated_committed(root):
    gi = read(os.path.join(root, ".gitignore"))
    return not re.search(r"^\s*(?:\*\*/)?\*\.g\.dart\s*$", gi, re.M)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    pubspec = read(os.path.join(root, "pubspec.yaml"))
    if not pubspec.strip():
        print("STACK: generic")
        return 0

    melos = os.path.exists(os.path.join(root, "melos.yaml")) or \
        bool(re.search(r"^melos:", pubspec, re.M))
    is_flutter = bool(re.search(r"^\s+sdk:\s*flutter\s*$", pubspec, re.M))
    names = deps_of(pubspec)
    fvm = any(os.path.exists(os.path.join(root, p)) for p in (".fvmrc", ".fvm/fvm_config.json"))
    fl = "fvm flutter" if fvm else "flutter"
    dt = "fvm dart" if fvm else "dart"
    tool = fl if is_flutter else dt
    codegen = "build_runner" in names
    l10n = is_flutter and (os.path.exists(os.path.join(root, "l10n.yaml")) or
                           bool(re.search(r"^\s+generate:\s*true\s*$", pubspec, re.M)))
    has_it = os.path.isdir(os.path.join(root, "integration_test"))

    print(f"STACK: {'flutter' if is_flutter else 'dart'}")
    print(f"## Stack profile ({'Flutter' if is_flutter else 'Dart'}) - generated by "
          "scripts/detect_stack.py; do not hand-edit")
    print(f"- Toolchain: `{fl}` / `{dt}`"
          + (" (FVM-pinned - never call bare flutter/dart)" if fvm else ""))
    if melos:
        print("- Monorepo: melos - run commands per package, or via `melos run <script>`")
    if is_flutter:
        plats = [p for p in PLATFORMS if os.path.isdir(os.path.join(root, p))]
        print(f"- Platforms: {', '.join(plats) or 'none detected'}")
        fv = flavors(root)
        print(f"- Flavors: {', '.join(fv) if fv else 'none detected'}")
    sm = pick(names, STATE_MGMT)
    print(f"- State management: {', '.join(sm) or 'none detected (setState / built-in)'}"
          " - follow the existing pattern; introducing another is an ADR-level decision")
    rt = pick(names, ROUTING)
    if is_flutter:
        print(f"- Routing: {', '.join(rt) or 'Navigator (none detected)'}")
    if codegen:
        committed = ("committed - stage them with the source" if generated_committed(root)
                     else "git-ignored - never commit them")
        print(f"- Codegen: build_runner ({', '.join(pick(names, GENERATORS)) or 'generators unknown'})"
              f"; generated files are {committed}")
    if is_flutter:
        print("- Localisation: " + ("gen-l10n (ARB files) - user-visible strings go in ARB, "
                                    "never hard-coded" if l10n else "none detected"))
    st = pick(names, STORAGE)
    if st:
        print(f"- Storage: {', '.join(st)}")
    tl = pick(names, TEST_LIBS)
    print(f"- Tests: `test/` ({', '.join(tl) or 'flutter_test only'})"
          + ("; integration `integration_test/`" if has_it else "; no integration_test/")
          + ("; golden files present" if is_flutter and has_goldens(root) else ""))
    ln = pick(names, LINTS)
    if os.path.exists(os.path.join(root, "analysis_options.yaml")):
        print(f"- Lints: {', '.join(ln) or 'custom'} via analysis_options.yaml")
    else:
        print("- Lints: no analysis_options.yaml")
    print("- Commands:")
    print(f"  - format:   `{dt} format --set-exit-if-changed <changed .dart files>`")
    print(f"  - analyze:  `{tool} analyze <changed paths>` (introduce no new issues)")
    if codegen:
        print(f"  - codegen:  `{dt} run build_runner build --delete-conflicting-outputs`"
              " after editing any annotated source")
    if l10n:
        print(f"  - l10n:     `{fl} gen-l10n` after editing ARB files")
    print(f"  - test (targeted): `{tool} test <test files>`")
    print(f"  - test (full):     `{tool} test --coverage`"
          + ("  (monorepo: `melos run test` if defined)" if melos else ""))
    if has_it:
        print(f"  - integration:     `{fl} test integration_test -d <device>`")
    shared = ["pubspec.yaml", "pubspec.lock"]
    if l10n:
        shared.append("ARB files")
    if rt:
        shared.append("router config")
    if {"injectable", "get_it"} & names:
        shared.append("DI registration")
    if is_flutter:
        shared.append("lib/main*.dart")
    print(f"- Shared files (a task touching these is never parallel-safe): {', '.join(shared)}")
    if codegen:
        print("- A task editing annotated (codegen) sources is never parallel-safe: "
              "build_runner rewrites generated files across the package")
    print(f"- Generated (never hand-edit; excluded from review diffs): {' '.join(GENERATED_GLOBS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
