# `strata drafting fetch --mode`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` のいずれか |

## 役割

fetch がどの drafting の選択を前提に「DFlash2 drafter が必要か」を判定するかを指定します。`--if-needed` と併用すると、その選択で DFlash2 を使い、かつ drafter が未配置の場合だけ取得します。`--mode` 単独では取得を抑止しません。

## 使い方

```sh
strata drafting fetch --config ./run.json --mode dflash2 --if-needed
```

## 値と既定値

- parser は `drafting.MODES` を選択肢として指定しており、受理値は `auto`、`mtp`、`dflash2`、`off` です。値を省略した場合、`--config` があればその JSON の `drafting` 値を使い、なければ `normalize(None)` により `auto` になります。
- 存在しない値は argparse の choices 検査で拒否されます。別名はありません。
- `--mode` が明示されると、config の `drafting` 値より優先されます。

## 実行時の動作

`--mode` は config から得た model・backend・hardware 情報とともに drafting の選択判定へ渡されます。`auto` はモデル、engine/backend、GPU arch・VRAM などに応じて MTP または DFlash2 を選び、`mtp` と `off` はそれぞれその選択、`dflash2` は DFlash2 を要求します。要求先が未対応の条件や pack 未配置時の代替可否も含め、`needed` は選択が DFlash2 で pack が未配置の場合に真になります。

ただし fetch の通常動作は `needed` を条件にせず `drafting_fetch.ensure_for(...)` を呼びます。したがって `--mode off` や `--mode mtp` を指定しても、`--if-needed` を付けなければ DFlash2 drafter の取得処理を実行します。`--if-needed` があり `needed` が偽なら取得を省略し、「Nothing to download.」または JSON の `skipped: true` を返します。

config の `mtp: false` と `--mode auto` の組み合わせは `off` として扱われます。さらに `auto` / `mtp` は、`--no-split` がなく split engine がこの config の起動を引き受けると判定された場合、split 用 MTP を選ぶよう `mtp` に切り替わります。この調整後の mode が `needed` 判定に使われます。

## 適用条件と副作用

- `--config` を指定すると、config から data directory（`--data-dir` があればそちらが優先）、model/backend、drafting 設定を読みます。config がない場合の model/family 指定と、Strata が検出する hardware 情報も判定に影響します。
- `--mode` は選択・必要性の判定値であり、`--if-needed` なしの取得実行を止めるスイッチではありません。ネットワーク取得を望まない状況では実行しないでください。
- 実際に取得されると、データディレクトリ配下に drafter 用ファイルを取得・pack し、検証済みの出力を配置します。詳細な配置先や取得内容は `drafting_fetch.ensure_for` / `ensure` の処理に依存します。

## 出力とエラー

- fetch が成功すると、人向け出力は ready になったパスを表示し、`--output json` / `jsonl` では結果イベントを出します。進捗は `jsonl` の場合 progress event になります。
- `--if-needed` で不要と判定された場合は成功扱いで skip します。
- 取得・検証等で `DraftingError` または取得拒否が起きると、human 出力は stderr に `strata:` エラーを表示して終了値 5、機械向け出力は `ok: false` の error JSON を返します。`--throttle` による未取得 `None` は黙って skip する別経路です。

## 根拠

- parser、選択肢、config/default の説明: `terminal/strata_cli/drafting_cmd.py:19-38`。
- config と `--mode` の優先順位、`mtp: false` および split 判定による mode 調整、hardware 等の入力: `terminal/strata_cli/drafting_cmd.py:101-136`。
- 値の正規化と選択肢一覧: `terminal/strata_control/drafting.py:37-39`, `terminal/strata_control/drafting.py:882-885`。
- mode ごとの選択効果と hardware/model 条件: `terminal/strata_control/drafting.py:1527-1545`。
- 未配置判定: `terminal/strata_control/drafting.py:1611-1622`。
- `--if-needed` の skip と通常 fetch の呼び分け、出力・失敗コード: `terminal/strata_cli/drafting_cmd.py:243-301`。
- fetch による ensure 呼び出しと tuned drafter / stock drafter の fallback: `terminal/strata_control/drafting_fetch.py:349-373`。
- ダウンロード・pack の実処理: `terminal/strata_control/drafting_fetch.py:376-430`。
