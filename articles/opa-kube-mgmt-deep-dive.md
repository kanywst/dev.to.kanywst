---
title: "OPA & kube-mgmt: Gatekeeper前夜の「サイドカー」パターンを深掘りする (完全版)"
published: false
description: "2026年、Kubernetesのポリシー制御はGatekeeperが標準ですが、その原点である「OPA + kube-mgmt」の構成は、汎用的なポリシー配信基盤として今なお現役です。ConfigMapをOPAのメモリに同期するサイドカーの仕組み、Regoの評価プロセス、そしてアプリケーション認可への応用まで、ソースコードレベルで徹底解説します。"
tags: ["opa", "kubernetes", "policy-as-code", "gatekeeper", "sidecar", "rego"]
---

# イントロダクション: OPAは「ただの計算機」である

Kubernetesの世界で「ポリシー管理」といえば **OPA (Open Policy Agent)** です。
しかし、OPA自体は非常にシンプルです。一言で言えば、**「JSONを入力して、JSONを返すだけの関数（計算機）」** です。

*   **入力**: 「ユーザーAが、商品Bを買いたい」というデータ
*   **ルール**: 「在庫があればOK」というロジック（Rego言語）
*   **出力**: 「許可 (Allow)」または「拒否 (Deny)」

OPAは、Kubernetes専用ではありません。Linuxでも、SSHでも、あなたの自作アプリでも使えます。
なぜなら、OPAは **「今の世界の状況（Kubernetesの状態など）」を何も知らない** からです。

そこで登場するのが、今回の主役 **kube-mgmt** です。
これは、世間知らずのOPAに、Kubernetesの世界の情報をせっせと運び続ける **「専属の運び屋（Sidecar）」** です。

この記事では、Gatekeeperの影に隠れがちな、しかし汎用性最強のこのパターンを、内部実装や運用ノウハウを含めて500行超のボリュームで徹底的に深掘りします。

<!-- SECT1_END -->



# 1. 概念図解: OPAとkube-mgmtの関係



まずは、OPAとkube-mgmtがどう協力しているのか、その役割分担を見てみましょう。



### OPA = 「裁判官」

法律（ポリシー）と証拠（入力データ）に基づいて、判決を下します。しかし、裁判所から一歩も出ないので、世の中のニュース（Kubernetesの現状）を知りません。



### kube-mgmt = 「秘書」

裁判官の横にいて、常に外の世界（Kubernetes API）を監視しています。新しい法律（ConfigMap）ができたり、世の中の状況（Podの状態）が変わったりすると、すぐに裁判官に報告（Sync）します。



```mermaid

graph LR

    %% 定義

    classDef k8s fill:#e3f2fd,stroke:#2196f3,stroke-width:2px;

    classDef pod fill:#fff3e0,stroke:#ff9800,stroke-width:2px,stroke-dasharray: 5 5;

    classDef opa fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px;

    classDef mgmt fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;

    classDef user fill:#fff,stroke:#333,stroke-width:1px;



    subgraph K8s [☸️ Kubernetes World]

        CM["📜 ConfigMap\n(新しい法律)"]:::k8s

        Resources["📦 Pods/Services\n(世の中の状況)"]:::k8s

    end



    subgraph Pod [🏠 Sidecar Pod]

        direction TB

        

        subgraph Sidecar [秘書]

            Mgmt["🕵️ kube-mgmt"]:::mgmt

        end

        

        subgraph Main [裁判官]

            OPA["🧠 OPA Engine"]:::opa

            Memory[("🧠 メモリ\n(知識)")]:::opa

        end

        

        Mgmt -->|Sync (コピー)| Memory

    end



    User[👤 Client]:::user -->|「これやっていい？」| OPA

    OPA -->|参照| Memory

    OPA -->|「ダメです」| User



    %% フロー

    CM -.->|Watch| Mgmt

    Resources -.->|Watch| Mgmt

```



1.  **Watch**: `kube-mgmt` はKubernetes APIを監視し続けます。

2.  **Sync**: 変更があれば、OPAのメモリにデータをPUTします。

3.  **Decide**: クライアント（アプリ）がOPAに問い合わせた時、OPAはメモリ上の最新情報を使って即座に判断します。



<!-- SECT2_END -->

# 2. Deep Dive: kube-mgmt の内部実装

`kube-mgmt` は魔法を使っているわけではありません。その内部は、Kubernetesの標準的な **Controllerパターン** で実装されています。

## 2-1. ポリシーの同期 (Policy Sync)

`kube-mgmt` は、特定のラベル（デフォルトでは `openpolicyagent.org/policy=rego`）がついたConfigMapを監視します。

*   **検知**: ConfigMapが作成・更新されると、その `data` フィールドの中身（Regoコード）を読み取ります。
*   **変換**: OPAのREST API (`PUT /v1/policies/<id>`) を叩き、Regoコードを登録します。
*   **エラーハンドリング**: もしRegoに構文エラーがある場合、ConfigMapの `status` (annotation) にエラー情報を書き込みます。これにより、ユーザーは `kubectl describe configmap` でエラーを確認できます。

## 2-2. データの同期 (Data Sync)

ポリシーだけでなく、JSONデータ（例：ユーザーごとの権限リスト）も同期できます。
ラベル `openpolicyagent.org/data=opa` がついたConfigMapが対象です。

*   **パス**: OPAの `PUT /v1/data/<path>` にマッピングされます。
*   **構造**: ConfigMapのデータ構造がそのままOPAのデータ構造になります。

## 2-3. Kubernetesリソースの同期 (Replication)

これが最も強力な機能です。`--replicate=<group>/<version>/<kind>` フラグを指定すると、指定されたKubernetesリソースをOPAのメモリ上にミラーリングします。

*   **仕組み**: Kubernetesの `SharedInformer` を使い、リソースの変更イベント（Add/Update/Delete）を受け取ります。
*   **保存先**: OPAの `data.kubernetes.<kind>` 以下に保存されます。
    *   例: `data.kubernetes.pods.default.my-pod`
*   **用途**: 「同じNamespaceにあるServiceのリストを取得して、アクセス可否を決める」といった **コンテキスト指向のポリシー** が書けるようになります。

<!-- SECT3_END -->

# 3. OPA内部アーキテクチャ: 高速判定の秘密

OPAがなぜ高速なのか、その内部構造を見てみましょう。

### 3-1. In-Memory Store (Radix Tree)

OPAは全てのデータ（ポリシーとJSONデータ）をメモリ上に持ちます。
このデータは **Radix Tree（基数木）** という構造で最適化されて格納されています。

*   **検索**: パス指定（例：`data.example.allow`）による検索は、ハッシュマップと同等かそれ以上に高速です。
*   **共有**: 親ノードを共有することで、メモリ消費を抑えています。

### 3-2. Compiler & Evaluation

Regoで書かれたポリシーは、実行時にインタプリタで解釈されるわけではありません。
ロード時に **AST（抽象構文木）** にパースされ、さらに **中間表現** にコンパイルされます。

1.  **Parse**: 文字列としてのRegoをASTに変換。
2.  **Compile**: 参照の解決、型のチェック、インデックスの構築。
3.  **Evaluate**: リクエスト（Input）が来た時、コンパイル済みのルールを適用。

この「事前コンパイル」と「インメモリストア」の組み合わせにより、OPAはミリ秒単位の応答速度を実現しています。

<!-- SECT4_END -->

# 4. Deep Dive: Gatekeeperとの決定的な違い

「でも今はGatekeeperがあるじゃん？」その通りです。
しかし、アーキテクチャを見ると「使い所」の違いが明確になります。

```mermaid
graph TB
    subgraph Gatekeeper_Arch [🛡️ Gatekeeper (Centralized)]
        GC[Gatekeeper Controller]
        CRD[Custom Resource Definition]
        API[K8s API Server]
        
        GC -- "Webhook" --> API
        GC -- "Watch" --> CRD
        Note1[Kubernetes全体の\n門番として機能]
    end

    subgraph Sidecar_Arch [🤝 kube-mgmt (Decentralized)]
        AppPod[Application Pod]
        LocalOPA[OPA Sidecar]
        LocalMgmt[kube-mgmt Sidecar]
        
        AppPod -- "localhost:8181" --> LocalOPA
        LocalMgmt -- "Sync" --> LocalOPA
        Note2[アプリごとの\n専属アドバイザー]
    end
    
    style Gatekeeper_Arch fill:#e1f5fe
    style Sidecar_Arch fill:#fff3e0
```

### アーキテクチャ比較表

| 特徴 | kube-mgmt (Sidecar) | Gatekeeper (Controller) |
| :--- | :--- | :--- |
| **配置場所** | 各Podにサイドカーとして配置 | クラスタ中央に1つ |
| **ポリシー定義** | ConfigMap (Rego直書き) | CRD (ConstraintTemplate) |
| **主な用途** | **アプリケーション認可** (Microservice Authz) | **K8s Admission Control** (デプロイ制限) |
| **通信経路** | localhost (超高速・低遅延) | Webhook (ネットワーク経由) |
| **スケーラビリティ** | Pod数に比例してリソース消費増 | コントローラの負荷集中に注意 |
| **データ同期** | 必要なデータだけ選んで同期可能 | 全データをキャッシュする必要がある場合も |

Gatekeeperは「Kubernetesを守る」ためのものですが、kube-mgmtは **「あなたのアプリケーションが、ポリシー判断を外部委譲する」** ための基盤として、今なお最強の選択肢です。

<!-- SECT5_END -->

# 5. Rego言語入門: "もし〜ならOK" の世界

OPAの心臓部であるRego言語について、少し詳しく見てみましょう。
Regoは、**「データに対するクエリ」** です。SQLに似ていますが、JSONのような階層データに対して強力です。

### 基本構文

```rego
package example

default allow = false

# 複数の条件（AND）
allow {
    input.method == "GET"
    input.user == "admin"
}

# 別の条件（OR）
allow {
    input.method == "POST"
    input.user == "superuser"
}
```

*   `allow` ブロックの中に書かれた条件は **AND** 条件です（すべて満たす必要がある）。
*   複数の `allow` ブロックを書くと **OR** 条件になります（どれか一つでも満たせばOK）。

### データの参照

`kube-mgmt` で同期したデータは、`data` グローバル変数から参照できます。

```rego
# data.kubernetes.pods を参照して、
# "同じNamespaceのPodなら許可" するルール
allow {
    # 入力されたPod名
    target_pod_name := input.target_pod
    
    # メモリ上のPodリストから検索
    pod := data.kubernetes.pods[input.namespace][target_pod_name]
    
    # 条件チェック
    pod.metadata.labels.app == "trusted-app"
}
```

このように、**「今のクラスタの状態」を条件に組み込める** のが、OPA + kube-mgmtの真骨頂です。

<!-- SECT6_END -->

# 6. Hands-on: Kindで動かしてみよう

実際に、Mac上のKind (Kubernetes in Docker) 環境で、OPAとkube-mgmtを動かしてみましょう。

### Step 0: 準備

Kindクラスタを作成し、OPA用のNamespaceを作ります。

```bash
# クラスタ作成
kind create cluster --name opa-test

# Namespace作成 (kube-mgmtが監視する対象)
kubectl create namespace opa-policy
```

### Step 1: Podの定義 (opa.yaml)

「OPA」と「kube-mgmt」が仲良く同居するPodを作ります。

```yaml
cat <<EOF > opa.yaml
apiVersion: v1
kind: Pod
metadata:
  name: opa-sidecar-demo
  labels:
    app: opa
spec:
  containers:
  # 1. 主役: OPA (8181ポートで待ち受け)
  - name: opa
    image: openpolicyagent/opa:latest
    args:
    - "run"
    - "--server"
    - "--addr=localhost:8181"
    ports:
    - containerPort: 8181

  # 2. 脇役: kube-mgmt (K8sを見てOPAに教える)
  - name: kube-mgmt
    image: openpolicyagent/kube-mgmt:0.11
    args:
    - "--policies=opa-policy"       # このNamespaceのConfigMapを監視するよ
    - "--opa-url=http://localhost:8181/v1" # 隣のOPAへの連絡先
EOF

kubectl apply -f opa.yaml
```

### Step 2: ポリシーの定義 (policy.yaml)

ConfigMapにRegoを書きます。`openpolicyagent.org/policy: rego` というラベルが、「これはOPA用のルールだよ」という合図です。

```yaml
cat <<EOF > policy.yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: example-policy
  namespace: opa-policy # kube-mgmtが監視するNamespace
  labels:
    openpolicyagent.org/policy: rego
data:
  main.rego: |
    package example

    default allow = false

    # "admin" ユーザーなら許可
    allow {
        input.user == "admin"
    }
EOF

kubectl apply -f policy.yaml
```

### Step 3: 動作確認

`kube-mgmt` がConfigMapを検知し、OPAにポリシーを注入しているはずです。
ローカルからOPAに問い合わせて確認してみましょう。

```bash
# ポートフォワードでローカルからアクセス可能にする
kubectl port-forward opa-sidecar-demo 8181:8181 &
PID=$!

# 少し待つ
sleep 2

echo "--- Test 1: Guest User ---"
# 拒否されるケース (user: guest)
curl -X POST http://localhost:8181/v1/data/example/allow \
  -d '{"input": {"user": "guest"}}'
# 結果: {"result": false}

echo "\n--- Test 2: Admin User ---"
# 許可されるケース (user: admin)
curl -X POST http://localhost:8181/v1/data/example/allow \
  -d '{"input": {"user": "admin"}}'
# 結果: {"result": true}

# 後始末
kill $PID
```

### Step 4: ポリシーの動的更新

ConfigMapを書き換えるだけで、Podの再起動なしにポリシーが反映されることを確認します。

```bash
# ポリシーを「guestでもOK」に書き換え
kubectl patch configmap example-policy -n opa-policy --type merge -p '{"data":{"main.rego":"package example\ndefault allow = true"}}'

# 再確認 (即座に反映されるはず)
kubectl port-forward opa-sidecar-demo 8181:8181 &
PID=$!
sleep 2

echo "--- Test 3: Guest User (After Update) ---"
curl -X POST http://localhost:8181/v1/data/example/allow \
  -d '{"input": {"user": "guest"}}'
# 結果: {"result": true}

kill $PID
```

<!-- SECT7_END -->

# 7. 本番運用における注意点とベストプラクティス

最後に、本番環境でこの構成を採用する際の重要なポイントをまとめます。

### 7-1. メモリ使用量の見積もり
`kube-mgmt` で `--replicate` を使って大量のリソース（数千個のPodなど）を同期する場合、OPAのメモリ使用量が急増します。
OPAは全てのデータをインメモリで保持するため、JVMのようなGCチューニングこそ不要ですが、PodのMemory Limitは余裕を持って設定する必要があります。

**計算式（目安）**:
`Memory = (JSONデータサイズ x 20) + (インデックスオーバーヘッド)`
JSONの生データの約20倍程度のメモリを消費すると見積もるのが安全です。

### 7-2. 整合性 (Eventual Consistency)
ConfigMapを更新してから、kube-mgmtがそれを検知し、OPAに反映されるまでには **数秒〜数十秒のラグ** があります。
Kubernetesの `Watch` イベントは非同期であり、ネットワークの遅延も含まれます。
「今更新したポリシーが、次のミリ秒のリクエストに即座に適用される」ことを期待してはいけません。結果整合性（Eventual Consistency）を受け入れる設計にしましょう。

### 7-3. デバッグの難しさ
「なぜ拒否されたのか？」が分からない時、デバッグは困難を極めます。
OPAには `decision_logs` という機能があり、判定結果のログを出力できます。これを有効にして、Fluentdなどで収集する仕組みを最初から入れておくことを強く推奨します。

```yaml
# OPAの設定例 (opa-config.yaml)
decision_logs:
  console: true
```

また、`opa eval` コマンドを使ったローカルでのユニットテストも必須です。Regoファイルに対するテストコード (`_test.rego`) を書き、CIで回すのがモダンな開発フローです。

# まとめ: 適材適所の "Policy Engine"

*   **Kubernetes自体のガードレール**（例：特権コンテナ禁止）を作りたい → **Gatekeeper** を使いましょう。
*   **アプリケーションごとの認可ロジック**（例：課金ユーザーだけがこのAPIを叩ける）をPod内で完結させたい → **OPA + kube-mgmt** が輝きます。

2026年になっても、この「ConfigMapをWatchしてSyncする」というシンプルなパターンは、分散システムのデータ同期における一つの正解であり続けています。
古くからある技術だからこそ、枯れていて、頼りになるのです。

## Cleanup

```bash
kind delete cluster --name opa-test
rm opa.yaml policy.yaml
```

## 参考文献
*   [OPA kube-mgmt GitHub](https://github.com/openpolicyagent/kube-mgmt)
*   [Gatekeeper Project](https://open-policy-agent.github.io/gatekeeper/website/)
*   [Open Policy Agent Documentation](https://www.openpolicyagent.org/docs/latest/)
