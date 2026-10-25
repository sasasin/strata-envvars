# `strata components backends`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components backends` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/targets.py` |
| オプション | `--output`（値: `human` または `json`、既定値: `human`） |

## 役割

プロジェクトが対応対象としている OS × backend の組み合わせを表示し、現在のマシンの OS・CPU アーキテクチャが各 backend の platform 一覧に含まれるかを示します。ここで表示するのはソースに定義された対応表です。GPU を検出したり、導入済み engine を調べたり、組み合わせの実機動作を検証したりするコマンドではありません。parser は `components backends` を「コミットしている組み合わせと、そうでないもの」の一覧として登録しています（`strata_cli/cli.py:129-131`）。

## 使い方

```sh
# 人が読む形式で対応表を表示
strata components backends

# 自動処理向けに同じ対応表を JSON で出力
strata components backends --output json
```

`--output` はこのサブコマンド固有で、値は `human` / `json`、省略時は `human` です（`strata_cli/cli.py:129-131`）。個別の出力形式は [`--output`](--output.md)、ヘルプは [`--help`](--help.md) を参照してください。

## 表示内容と対応範囲

現在の実装では対応表は次のとおりです（`strata_control/targets.py:20-29`）。コマンドは backend 名でソートして表示します（`strata_cli/cli.py:2048-2050`）。

| Backend | 対象 platform |
| --- | --- |
| `cpu` | `macos-arm64`, `macos-x86_64`, `windows-x86_64`, `linux-x86_64` |
| `cuda` | `windows-x86_64`, `linux-x86_64` |
| `hip` | `windows-x86_64`, `linux-x86_64` |
| `metal` | `macos-arm64` |
| `sycl` | `linux-x86_64` |

現在の platform は `platform.system()` を `macos` / `linux` / `windows` に対応付け、CPU 名を正規化して `<os>-<arch>` 形式にします。`Darwin` は `macos`、`aarch64` は `arm64`、`amd64` は `x86_64` として扱います（`strata_control/targets.py:31-39`）。一覧の各行には platform の配列と、現在の platform が配列に含まれるかを表す `here` 値が付きます（`strata_cli/cli.py:2047-2050`）。

human 出力では現在の platform、backend ごとの platform 一覧、および `supported here` / `not supported here` を表示します。JSON 出力は `schema_version: 1`、`ok: true`、`host`、`matrix` を含みます（`strata_cli/cli.py:2051-2061`、`strata_cli/cli.py:535-542`）。未対応の組み合わせは試行しない旨も human 出力に表示されます。

## 実行モードと副作用

このコマンドに起動モードや更新モードはありません。引数解析後、`_run` が `components backends` を `_components_backends` に渡し、対応表を組み立てて標準出力へ表示します（`strata_cli/cli.py:2129-2133,2044-2061`）。この処理でファイルの読み書き、ダウンロード、engine の起動は行いません。コマンド登録上も親 `components` は installed component inventory と説明されます（`strata_cli/cli.py:114-115`）が、このサブコマンド自体の処理は対応表と現在の platform の比較です。

## 注意点と制約

- 表示上の `supported here` は、現在の platform 文字列が対応表に含まれるという意味です。GPU の有無、driver、個別 engine package の導入状況、実機での qualification を示しません。human 出力も、一覧にあって実機 qualification が済んでいない組み合わせは「prepared, not claimed」と説明し、`packaging/README.md` を案内しています（`strata_cli/cli.py:2059-2060`）。実際の build・qualification 状況は調査対象ソースの `packaging/README.md` を参照してください。
- `platform.system()` が `Darwin` / `Linux` / `Windows` 以外の場合、platform 判定関数は `ComponentError` を送出します（`strata_control/targets.py:31-35`）。このサブコマンドでその例外を整形する分岐は確認できません。
- ソース parser から確認した利用可能な `--output` 値は `human` / `json` です。CLI の実行や `--help` 表示は補助資料としても実施していません。

## 関連文書

- [`strata components` コマンド概要](../README.md)
- [`strata components engine --backend`](../engine/--backend.md) — ローカル engine 確認で backend を指定するオプション。
- [CLI オプション索引](../../../README.md) — `components plan`、`engine`、`update` を含む同階層の予定文書一覧。

## 根拠

- `strata_cli/cli.py:114-140` — `components` 階層と `backends` / `--output` parser 定義。
- `strata_cli/cli.py:2044-2061` — 対応表の組み立て、human / JSON 出力、qualification に関する案内。
- `strata_cli/cli.py:2129-2133,535-542` — サブコマンドの振り分けと共通 JSON 成功出力。
- `strata_control/targets.py:20-39` — 固定の backend matrix と現在 platform の正規化。
- `packaging/README.md:12-27` — target ごとの build・実機確認状況と明示された未対応領域。
