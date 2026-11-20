FROM rust:1.100-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN groupadd -r -g 10001 streamops && useradd -r -u 10001 -g streamops streamops
COPY --from=builder /app/target/release/streamops-intent-engine /usr/local/bin/streamops-intent-engine
USER streamops
EXPOSE 8081
ENV INTENT_LISTEN_ADDR=0.0.0.0:8081
ENTRYPOINT ["streamops-intent-engine"]
