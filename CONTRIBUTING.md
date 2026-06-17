# Contributing to Tent of Trials

Thank you for your interest in contributing. Please follow the guidelines below to ensure a smooth process for everyone.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [PR Workflow](#pr-workflow)
- [Build Diagnostics](#build-diagnostics)
- [Code Style](#code-style)

## Prerequisites

The build system checks for these tools at runtime. Install any that are missing for the modules you plan to touch:

| Tool   | Minimum version | Module(s)             |
|--------|-----------------|-----------------------|
| Python | 3.8+            | Build system          |
| Rust   | 1.70+           | backend               |
| Node   | 22.x            | frontend              |
| Go     | 1.22+           | market                |
| GCC    | 11+             | frailbox (C)          |
| G++    | 11+             | engine (C++)          |
| CMake  | 3.28+           | engine (C++)          |
| Make   | 4.3+            | frailbox              |
| JDK    | 21+             | compliance (Java)     |
| Ruby   | 3.0+            | v2-market-stream      |
| Lua    | 5.4+            | nfc-scanner, tools    |
| GHC    | 9.4+            | openapi-haskell       |

## Getting Started

Clone the repository and install dependencies for the modules you plan to build:

```bash
git clone https://github.com/lobster-trap/TentOfTrials
cd TentOfTrials

### Repo tooling (Python)
sudo apt update
sudo apt install python3

### Backend (Rust)
sudo apt update
sudo apt install -y build-essential pkg-config curl protobuf-compiler libssl-dev
curl https://sh.rustup.rs -sSf | sh -s -- -y
source "$HOME/.cargo/env"
cargo fetch

### Frontend (TypeScript / React)
sudo apt update
sudo apt install -y curl ca-certificates gnupg
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
npm install

### market (Go)
sudo apt update
sudo apt install -y golang-go
go mod download

### frailbox (C)
sudo apt update
sudo apt install -y build-essential make gcc linux-libc-dev

### engine (C++)
sudo apt update
sudo apt install -y build-essential g++ cmake
# If Ubuntu's cmake is older than 3.28, install via snap:
sudo snap install cmake --classic

### compliance (Java)
sudo apt update
sudo apt install -y openjdk-21-jdk

### market v2 (Ruby)
sudo apt update
sudo apt install -y ruby-full ruby-dev build-essential redis-server
gem install eventmachine em-websocket-client redis sinatra

### scans (Lua)
sudo apt update
sudo apt install -y lua5.4 luarocks build-essential libi2c-dev i2c-tools
sudo luarocks install periphery
sudo luarocks install crypto

### openapi (Haskell)
sudo apt update
sudo apt install -y ghc cabal-install zlib1g-dev
cabal update
cabal install aeson text unordered-containers bytestring time directory filepath random network wai warp wai-logger http-types yaml aeson-keymap

### openapi-tools (Lua)
sudo apt update
sudo apt install -y lua5.4 luarocks build-essential
sudo luarocks install lua-yaml
sudo luarocks install http
sudo luarocks install crypto

### Install packages for all modules at once
sudo apt update
sudo apt install -y build-essential curl ca-certificates gnupg pkg-config libssl-dev protobuf-compiler make gcc g++ cmake linux-libc-dev openjdk-21-jdk golang-go ruby-full ruby-dev redis-server lua5.4 luarocks libi2c-dev i2c-tools ghc cabal-install zlib1g-dev
```

### Build

```sh
python3 build.py              # Build all modules
python3 build.py --clean      # Clean all artifacts
python3 build.py --module backend,frontend  # Build specific modules
python3 build.py --release    # Release mode (Rust only)
```

## PR Workflow

1. **Fork** the repository on GitHub.
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b my-feature-branch
   ```
3. **Make your changes** and commit them with a descriptive message:
   ```bash
   git add <files>
   git commit -m "Brief description of the change"
   ```
4. **Run the build** locally to verify everything compiles:
   ```bash
   python3 build.py
   ```
5. **Commit the diagnostic artifacts** produced by the build (see [Build Diagnostics](#build-diagostics)).
6. **Push** your branch:
   ```bash
   git push origin my-feature-branch
   ```
7. **Open a pull request** on GitHub. Use the [pull request template](.github/pull_request_template.md) and fill out all required sections.

## Build Diagnostics

Each run of `python3 build.py` writes an encrypted diagnostic bundle into the `diagnostic/` directory. The filename is derived from the current commit hash: `build-<commit-8-chars>.logd`, accompanied by a `build-<commit-8-chars>.json` metadata file.

**Diagnostic artifacts must be committed and included in every PR.** This is required so reviewers can verify the build environment. The repository includes a stub in `diagnostic/` showing the expected shape.

The pull request checklist includes an item you can tick if you would like the diagnostic files removed before merging.

## Code Style

- This project uses an `.editorconfig` file to define basic formatting rules (indentation, charset, trailing whitespace). Ensure your editor supports EditorConfig and picks up the settings automatically.
- Write clear, concise commit messages.
- Keep changes scoped to the purpose of the PR; avoid unrelated cleanup.
- Follow the conventions of the language you are working in — match the style of existing code in the module you are touching.
- Do not commit generated build artifacts (except the required diagnostic files).
