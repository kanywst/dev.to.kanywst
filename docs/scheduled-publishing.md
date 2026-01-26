# 予約投稿システム (Scheduled Publishing)

このプロジェクトでは、GitHub Actions を使用して dev.to への予約投稿を実現しています。

## 仕組み

1. **GitHub Action (`schedule.yml`)**: 毎時0分に起動します。
2. **検知スクリプト (`publish_scheduler.py`)**: 全記事の Frontmatter を確認し、以下の条件を満たす記事を特定します。
   - `published: false` である
   - `date` (公開予定日時) が現在時刻（UTC）を過ぎている
3. **自動更新**: 条件に合致した記事を `published: true` に書き換え、リポジトリにコミット & Push します。
4. **自動デプロイ**: 上記の Push をトリガーに、既存の `publish.yml` が起動し、dev.to へ記事が公開されます。

## 予約投稿の手順

記事の Frontmatter を以下のように設定して、`main` ブランチに Push してください。

```markdown
---
title: "記事のタイトル"
published: false             # 予約時は必ず false に設定
date: "2026-02-01T09:00:00Z"  # 公開したい未来の時刻を UTC で指定
tags:
  - tech
  - automation
---
```

### 注意点

- **時刻指定**: `date` は ISO 8601 形式（例: `2026-02-01T09:00:00Z`）で記述してください。タイムゾーンの指定がない場合は UTC とみなされます。
- **実行間隔**: GitHub Actions のスケジュール実行（cron）は毎時0分に設定されています。指定時刻を過ぎた後の最初の実行タイミングで公開されます。
- **手動実行**: すぐに公開状況を確認したい場合は、GitHub リポジトリの [Actions] タブから `Schedule Publisher` ワークフローを手動で実行することも可能です。

## トラブルシューティング

もし予約時刻を過ぎても公開されない場合は、以下の点を確認してください。
- `published` が `false` になっているか（既に `true` の場合はスキップされます）。
- `date` の形式が正しいか。
- `schedule.yml` の実行ログにエラーが出ていないか。
