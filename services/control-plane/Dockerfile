FROM golang:1.24 AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /streamops-control-plane .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /streamops-control-plane /streamops-control-plane
EXPOSE 8000
ENTRYPOINT ["/streamops-control-plane"]
