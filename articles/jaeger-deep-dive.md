---
title: "Jaeger Deep Dive: v2 アーキテクチャと分散トレーシングの進化"
published: false
description: "CNCF Graduated プロジェクトである Jaeger の内部実装を、最新の v2 アーキテクチャ (OpenTelemetry Collector ベース) を中心に解説。分散トレーシングの仕組みと、Storage Plugin の実装詳細を図解します。"
tags:
  - jaeger
  - opentelemetry
  - observability
  - distributed-tracing
  - deep-dive
date: '2026-03-10T09:00:00Z'
---

# Jaeger Deep Dive: v2 アーキテクチャと分散トレーシングの進化

マイクロサービスのデバッグにおいて、**分散トレーシング** は不可欠なツールです。
そのデファクトスタンダードである **Jaeger** は、現在大きな転換期を迎えています。

今回は、Jaeger v2 のソースコード（`jaeger/cmd/jaeger`）を読み解き、OpenTelemetry Collector をベースにした新しいアーキテクチャがどのように機能しているのかを解説します。

## 1. Jaeger v2 Architecture: OpenTelemetry との融合

かつての Jaeger は、Agent, Collector, Query, Ingester という個別のバイナリで構成されていました。
しかし、v2 では **OpenTelemetry Collector のディストリビューション** として再構築されました。

`jaeger/cmd/jaeger/internal/command.go` を見ると、その正体がよく分かります。

```go
// jaeger/cmd/jaeger/internal/command.go (概念コード)

func Command() *cobra.Command {
    // OpenTelemetry Collector の設定を構築
    settings := otelcol.CollectorSettings{
        Factories: Components, // Jaeger 独自のコンポーネントを注入
        // ...
    }
    // OTel Collector として起動
    return otelcol.NewCommand(settings)
}
```

これにより、Jaeger は単なるトレースバックエンドから、メトリクスやログも扱える汎用的なテレメトリーパイプラインへと進化しました。

```mermaid
graph TD
    %% Styling
    classDef otel fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef storage fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;

    subgraph "Jaeger v2 (OTel Collector)"
        Receiver[OTel Receiver<br>(gRPC/HTTP)]:::otel
        Processor[Batch Processor]:::otel
        Exporter[Storage Exporter]:::otel
        
        Receiver --> Processor --> Exporter
    end

    subgraph "Storage Backend"
        ES[(Elasticsearch)]:::storage
        Cassandra[(Cassandra)]:::storage
    end

    Exporter --> ES
    Exporter --> Cassandra
```

## 2. Storage Plugin System: 拡張性の要

Jaeger の強みは、バックエンドストレージの多様性にあります。
`jaeger/internal/storage/v1/api/spanstore/interface.go` に定義されているインターフェースが、その拡張性を支えています。

```go
type Writer interface {
    WriteSpan(ctx context.Context, span *model.Span) error
}

type Reader interface {
    GetTrace(ctx context.Context, query GetTraceParameters) (*model.Trace, error)
    FindTraces(ctx context.Context, query *TraceQueryParameters) ([]*model.Trace, error)
    // ...
}
```

新しいストレージバックエンドを追加したい場合は、この `Writer` と `Reader` インターフェースを実装するだけで済みます。
実際、`jaeger/internal/storage` ディレクトリには、Elasticsearch, Cassandra, Badger, Memory などの実装が並んでいます。

## 3. HotROD とサンプリング戦略

分散トレーシングの課題の一つに「データ量」があります。全リクエストを記録するとストレージが爆発するため、**サンプリング** が重要になります。

Jaeger は **Adaptive Sampling**（適応型サンプリング）をサポートしており、トラフィック量に応じて動的にサンプリングレートを調整できます。
これは `jaeger/internal/sampling` パッケージで実装されており、Collector が各サービスに対して「今は 10% だけ送ってくれ」といった指示を返します。

## まとめ

Jaeger v2 は、OpenTelemetry Collector という強力な基盤を得ることで、より柔軟で強力な可観測性プラットフォームへと進化しました。

- **Unified Binary**: 単一のバイナリで Agent, Collector, Ingester の役割を果たせる。
- **OTel Native**: OTel の豊富な Receiver/Exporter エコシステムをそのまま利用できる。
- **Backward Compatibility**: 従来の Jaeger クライアントからのデータも受け取れる。

これからトレーシングを導入するなら、この v2 アーキテクチャを理解しておくことが重要です。
次回は、エッジコンピューティングのための Kubernetes 拡張である **KubeEdge** について解説します。
