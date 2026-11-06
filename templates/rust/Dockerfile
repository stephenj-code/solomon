# Stage 1: build
# Using the actual target arch — ARC runners are ARM64 Jetsons, so this builds natively.
FROM rust:1.82-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
# Pre-fetch dependencies (cached layer — only invalidated if Cargo.toml changes)
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm src/main.rs
COPY src ./src
RUN touch src/main.rs && cargo build --release

# Stage 2: minimal runtime image (~10 MB)
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y libssl3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/__APP_NAME__ /usr/local/bin/app
RUN useradd -r -u 1000 appuser
USER 1000
EXPOSE 8000
CMD ["/usr/local/bin/app"]
