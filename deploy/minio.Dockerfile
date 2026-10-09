FROM golang:1.24.8-bookworm AS build
ENV GOMAXPROCS=2
WORKDIR /src
RUN git clone --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio.git . && test "$(git rev-parse HEAD)" = "9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a"
RUN CGO_ENABLED=0 go build -p 2 -trimpath -o /minio .
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/* && useradd -u 10001 -m minio && mkdir /data && chown minio:minio /data
COPY --from=build /minio /usr/local/bin/minio
USER minio
ENTRYPOINT ["minio"]
