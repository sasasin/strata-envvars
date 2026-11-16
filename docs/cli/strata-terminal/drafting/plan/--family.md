# `--family`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--family` |
| 別名 | なし |
| 値 | `NAME`（文字列。parser に選択肢制約・既定値なし） |

## 役割

モデルの run config がない場合に、DFlash2 drafter の計画で対象モデルの family を指定する。計画処理はこの値を `family` として drafter の適用可否・選択判定へ渡す。既存 run config がある場合はその `model_name` も判定材料となり、family が明示されれば実装上 family 名による判定が優先される。

## 使い方

```sh
# run config がないモデルについて、qwen family の計画を表示
strata drafting plan --family qwen --model IQ3_S
```

## 値と既定値

値は `NAME` 形式の任意文字列で、argparse による `choices`、型変換、既定値の指定はない。省略時は `None`。`--family` 自体の空文字や重複指定を個別に検証・拒否する処理は確認できず、通常の argparse の値取得結果が後段へ渡される。`--model` は family が不明な状態でモデル名を計画する場合に併用できる。

## 実行時の動作

`strata drafting plan` と `fetch` は共通 parser で `--family` を受け付けるが、この文書の対象である `plan` は `_inputs()` が返す `family` を drafter の `choice_of()` に渡し、結果に `choice` と `drafter` などを含む計画を作る。family が `None` でなければ `supported_model()` はモデル名ではなく family を小文字化して対応表と照合する。対応する値は `qwen`、`gyro`、`unsloth`。それ以外は DFlash2 対象外となり、計画上の選択は環境などに応じて MTP へ回る。対応 family でも engine build とハードウェアが DFlash2 を実行できることが必要で、mode、モデル、backend、カード条件も選択結果に関わる。

値の大文字小文字は family 判定時に小文字化される。`--config` を渡したときは run config のモデル情報・引数なども参照されるが、family が明示されている場合の DFlash2 対象判定は family 値を基準にする。`--mode` があればその選択を使い、なければ config の `drafting` 設定が使われる。

この plan 経路はネットワーク取得を行わず、JSON/JSONL 指定時は計画結果を JSON として出力し、通常は説明文または計画行を stdout に出して終了コード 0 を返す。`--family` 固有の validation error や警告経路は確認できない。

## 適用条件と副作用

family は DFlash2 が対象とするモデルかの判定材料であり、値を受理しただけで DFlash2 の実行が保証されるわけではない。エンジンの build 対応、backend・カード対応、drafter の導入状態、mode などの条件で別の drafter が選択されうる。plan parser は `--config`、`--model`、`--mode`、`--no-split` も受理する。`--no-split` を付けない場合、条件を満たす all-cards split engine 経路では MTP を使う計画に切り替わりうる。

`plan` 自体は何もダウンロードしない。ソースのモジュール説明は明示的な `fetch` のみが取得処理に進み、start はダウンロードしないとしている。

## 根拠

- `strata_cli/drafting_cmd.py:19-38` — `drafting plan` の parser 登録。`--family` は plan/fetch 共通で値制約なし、`--config`・`--model`・`--mode` 等も同じ parser にある。
- `strata_cli/drafting_cmd.py:117-134` — config、model 名、mode とともに `a.family` を計画入力に保持する。
- `strata_cli/drafting_cmd.py:166-185` — plan の判定・結果生成と stdout/JSON 出力、正常終了。
- `strata_control/drafting.py:453-467` — 対応 family と、family 指定時に小文字化してモデル名判定に優先する処理。
- `strata_control/drafting.py:1364-1387` — family、engine、hardware 等に基づく DFlash2 可否と選択。
- `strata_control/drafting_fetch.py:1-8` — plan は取得せず、明示 fetch のみがダウンロードするという処理境界。
