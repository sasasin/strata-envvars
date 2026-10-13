# `STRATA_CPUINFO`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Docker 用 entrypoint が、ホスト CPU の AVX2 対応を警告する際に確認するファイルのパスを差し替えます。主用途は entrypoint のテスト用です。通常は `/proc/cpuinfo` を読み、AVX2 が確認できない場合に警告を stderr に出します。この変数は CPU 機能の検出結果やビルド設定を変更せず、警告を出すかどうかだけに影響します。

## 値と判定

`docker-entrypoint.sh` のシェル展開 `${STRATA_CPUINFO:-/proc/cpuinfo}` を使います。

| `STRATA_CPUINFO` | 調査対象のパス |
|---|---|
| 未設定 | `/proc/cpuinfo` |
| 空文字 | `/proc/cpuinfo`（`:-` は未設定または空文字で既定値を使う） |
| 空でない文字列 | その文字列をパスとして使用 |

パスが読み取り可能で、ファイルに行頭が `flags` の行が少なくとも1つある場合だけ、そのうち最初の行を調べます。最初の `flags` 行に小文字の `avx2` が `grep -w` で単語として見つからなければ、AVX2 非対応の警告を出します。ファイル全体や後続の `flags` 行から AVX2 を補って判定することはありません。読み取り不可、または `flags` 行がない場合は警告条件に入りません。

## 有効になる条件

この変数を参照するのは Strata の `docker-entrypoint.sh` です。Dockerfile はこのスクリプトをコンテナの `ENTRYPOINT` に指定しています。したがって Docker イメージの entrypoint 経由で起動するときに適用されます。通常の `setup.py` による CPU 判定、エンジン内の CPU dispatch、コンパイル時の ISA 選択をこの変数が制御する根拠はありません。

## 実行時の詳細

entrypoint の起動直後、モデル設定やサーバー起動処理より前に一度だけファイルを確認します。AVX2 が見つからない場合は、stderr に次の3行を出します。

```text
WARNING: this host CPU has no AVX2. The engine in this image is built for CPUs with AVX2, so it may stop
  with 'illegal instruction' (exit 132). Build the image on this machine (docker build), which compiles the
  engine for the CPU it runs on, and see docs/INSTALL.md (Older CPUs, experimental) for the older-CPU build.
```

この分岐は警告のみで、スクリプトを終了させません。`STRATA_CPUINFO` は entrypoint の後続コマンドへ明示的に引数として渡されず、リポジトリ内のほかの本番ソースにも参照がありません。`docs/INSTALL.md` は ready-made engine が AVX2 を必要とし、古い CPU 向けには setup が実機で実験的な build を行う旨を説明していますが、`STRATA_CPUINFO` 自体の説明はありません。

## 根拠

- `docker-entrypoint.sh:9-17` — 変数の既定パス、読み取り可否・`flags` 行・AVX2 判定、警告文と警告のみの処理。
- `Dockerfile:114-117` — Docker の `ENTRYPOINT` が `docker-entrypoint.sh` であること。
- `docs/INSTALL.md:139-151` — ready-made engine の AVX2 要件と、旧 CPU 向け setup build の説明。環境変数の挙動を説明する資料ではない。
