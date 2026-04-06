FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /clinical-decision-server ./cmd/server

FROM alpine:3.20

RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /clinical-decision-server .

EXPOSE 8090

ENTRYPOINT ["./clinical-decision-server"]
