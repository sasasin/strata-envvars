# `PARALLEL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Docker イメージの entrypoint が読む設定です。コンテナ起動時に `PARALLEL` が数値指定されると `strata launch --parallel N` に変換され、サーバーが同時に応答するリクエスト数として保存・適用されます。値が空か小文字 `auto` ならフラグを渡さず、起動側のカードに合わせた既定選択に任せます。通常の Strata エンジンが `PARALLEL` を直接読む実装は見つかりませんでした。Docker entrypoint の別コマンド分岐を通る `strata ...` や `sh` では設定変換を行いません（`docker/entrypoint.sh:53-56,169-195`）。環境値の評価は entrypoint が起動した時点で行われます。

## 値と判定

| 環境値 | Strata の処理 |
|---|---|
| 未設定または空文字 | `--parallel` を追加しない。launch の既定選択に任せる。既存プリセットがある場合、空値だけでは保存済みの parallel 設定を消さない。 |
| `auto`（小文字・完全一致） | `--parallel` を追加しない。空値と同じ経路。 |
| 整数として変換でき、1〜8 | `--parallel` の値として渡す。`int()` による変換なので、前後の空白や符号付き整数も受理される。 |
| 整数でない値 | `strata launch` の引数エラーとなり、通常は終了コード 2。entrypoint は失敗コードを表示してコンテナを終了する。 |
| 0 以下または 8 超 | launch の 1〜8 範囲外エラーとなる。 |

entrypoint は空文字でない限り値をそのまま一つの引数として渡し、`auto` との比較は大文字小文字を区別します。したがって `AUTO`、`2.0`、`2x` は特別扱いされず、整数変換に失敗します。`docker/entrypoint.sh:194`、`strata_cli/launch/cmd.py:65-72`。

## 有効になる条件

- Docker の標準サーバー起動経路で有効です。Docker Compose の NVIDIA / AMD / Intel 定義はいずれもホスト側の `PARALLEL` をコンテナ環境へ渡します（`docker/compose/docker-compose.nvidia.yml:16-21`、`docker/compose/docker-compose.amd.yml:16-21`、`docker/compose/docker-compose.intel.yml:16-21`）。
- 明示値は launch の `--parallel` として扱われ、カードに対して大きすぎても選択自体は維持されます。launch はカードの VRAM に基づく推奨値を超えた場合に警告します（`strata_cli/launch/cmd.py:238-239,373-376`、`strata_cli/launch/settings.py:215-228`）。
- DeepSeek-V4.1-Flash の multi-file モデル経路は複数並列スロットを使いません。1より大きい指定は「この Strata version では一度に一件」と警告され、`s.parallel` から取り除かれます（`strata_cli/launch/cmd.py:352-357`）。
- 保存済みのエンジン引数に `--batch` または `--slots` がある場合、サーバー側は profile の `parallel` から追加の batch 引数を作りません（`serve/server.py:3303-3308`）。

## 実行時の詳細

明示した値は launch の設定に反映され、プリセットの serving override に保存されます。entrypoint は新規・既存どちらのプリセットも `--save-preset` 付きで launch し、launch runner は指定された parallel をカード推奨値より優先して `parallel=N` として保存します。空値または `auto` のときは環境変数からの上書きがないため、新規起動ではカード別の推奨値が選ばれます。既存プリセットでは、保存済みの値がそのまま使われることがあります（`docker/entrypoint.sh:242-249`、`strata_cli/launch/runner.py:1476-1493,1502-1509`）。

サーバー起動時、設定の `parallel` が 2 以上なら `serve/server.py` は `--batch N` を engine 引数へ追加します。1、未設定、または `False` では追加しません。engine は `--batch` / `--slots` を batch 数として読みます（`serve/server.py:3303-3324`、`src/program/generate.cpp:3196-3197`）。従って 1 は単一リクエスト動作で、設定がない場合も既定は一件ずつです（`docs/BATCHING.md:1-10`）。複数スロットでは最大 N 件の会話が同時に decode され、空きスロットがなければ他のリクエストは待ちます（`docs/BATCHING.md:88-97`）。

Docker の無効値は entrypoint 自身の範囲検査では拒否されません。値が launch CLI に届いた後、`argparse` の型・範囲エラーになります。entrypoint は launch の非ゼロ終了を受けて phase を failed にし、`strata launch stopped with code ...` を stderr に出して終了します（`strata_cli/launch/cmd.py:65-72`、`docker/entrypoint.sh:273-291`）。

## 根拠

- Docker 側の入力と変換: `docker/entrypoint.sh:9-16,53-56,169-195,242-249,273-291`。
- launch の整数変換、上限検査と設定反映: `strata_cli/launch/cmd.py:65-72,100,238-239,352-357,373-376`。
- VRAM 推奨、範囲警告、保存済みプリセットへの反映: `strata_cli/launch/settings.py:52-62,215-228`、`strata_cli/launch/runner.py:1476-1509`。
- server から engine 引数への反映と既存引数の優先: `serve/server.py:3300-3324`、engine 側の引数取り込み: `src/program/generate.cpp:3196-3197`。
- 同時リクエストの説明と実行上の slot 上限に関する文書: `docs/BATCHING.md:1-10,88-97`。

`rg` で候補名の全参照を確認しました。実装上の環境入力は Docker entrypoint のみで、Compose は値を転送します。`docs/DOCKER.md` と `.env.example` は利用説明、テスト中の参照は fixture / assertion です。`strata_control/amd_four_card.py` の `PARALLEL` は Python 定数であり環境変数読み取りではありません。候補名の他の文字列出現はコメントや画面表記でした。
