# `--feed`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 文字列を1つ取る。parser に URL/path 形式の検証はない |

## 役割

このコマンドでは `--feed` の値は受理されますが、engine 切替には使われません。`use` parser は共通オプションとして `--feed` を登録する一方、実行時の `use` 分岐はインストール済み engine を列挙して切り替える処理へ進み、feed の選択・読み込み処理を通りません（`strata_cli/update_cmd.py:47-57, 84-87, 272-273, 378-394`）。

engine の切替元を変える目的では指定しないでください。`--feed` は feed を読む更新コマンド（`strata update` / `strata components update`）向けの共通 parser 登録が `use` にも含まれたものです。

## 使い方

```sh
strata components use newest
```

この `use` コマンドに `--feed` を付けても値は無視され、feed の取得や検証は起きません。`newest` はインストール済み一覧から、この PC で使える最新 engine を選ぶ指定です（`strata_control/engine_library.py:198-211`）。

## 値と既定値

- `--feed` は値を1つ取ります。共通 parser の定義は `default=None` で、値を文字列のまま保持します（`strata_cli/update_cmd.py:47-49`）。
- `use` の処理は `a.feed` を参照しないため、値が未指定でも指定されていても engine 選択結果は変わりません。空文字列や不正な URL/path も feed の値として検証されません（`strata_cli/update_cmd.py:272-273, 378-394`）。
- `STRATA_UPDATE_FEED` や前回使った feed source による既定値選択は、更新処理が呼ぶ `_feed_source()` にありますが、`use` 分岐はそこへ到達しません（`strata_cli/update_cmd.py:123-139, 272-287`）。

## 実行時の動作

`strata components use` は `--components-dir`（指定時）または既定の component 領域から engine を列挙し、位置引数と `--family` で対象を特定します。候補が1件で、この PC で実行可能なら `engine_library.use_engine()` が選択を切り替えます。ここで使う情報はローカルのインストール状態と hardware 情報であり、feed は参照しません（`strata_cli/update_cmd.py:244-256, 272-273, 378-394`; `strata_control/engine_library.py:180-211, 225-239`）。

切替はダウンロードや削除を行わず、以後に開始するモデルが選ぶ engine を変更します。実行中のモデルがある場合、`--wait` 等の条件に従い待機または切替拒否になります。選んだ engine が最新なら更新追従に戻り、古い版を選ぶ場合は pin されます（Qwen: `strata_control/engine_library.py:225-239`; `strata_control/updater.py:1303-1352`。DeepSeek: `strata_control/engine_library.py:265-289`）。これらは `--feed` の効果ではありません。

## 適用条件と副作用

- `--feed` 自体にネットワーク、ファイル読み込み、状態変更の副作用はありません。feed の URL/path が存在しない、または不正でも、このオプションを理由に失敗しません（`strata_cli/update_cmd.py:272-273, 378-394`）。
- コマンド本体はローカル engine の確認・切替を行います。切替時は component の更新状態を変更し、保存済み tuning preset を短い再確認の対象としてマークする場合があります（`strata_control/engine_library.py:180-195, 225-239`; `strata_control/updater.py:1303-1352`）。
- 異なる OS / GPU backend / driver 条件などで実行できない engine は切替できません（`strata_control/engine_library.py:59-81, 378-383`）。

## 出力とエラー

成功時は人向け出力で「すでに使用中」または切替先 engine、preset の扱い、更新追従状態を表示します。`--output json` / `jsonl` が指定される場合は構造化出力になります。いずれも `--feed` の値は表示や処理に使われません（`strata_cli/update_cmd.py:98-120, 384-394`）。

engine が見つからない、同じ version の候補が曖昧、または切替できない場合はエラーになります。通常の更新分岐の feed 読み込みエラー処理は存在しますが、`use` は feed を読まないため適用されません（`strata_control/engine_library.py:198-211, 225-261`; `strata_cli/update_cmd.py:272-287, 307-319`）。

## 根拠

- `strata_cli/update_cmd.py:47-57` — 共通 parser での `--feed` 定義
- `strata_cli/update_cmd.py:84-87` — `use` parser が共通オプションを登録する箇所
- `strata_cli/update_cmd.py:123-139, 272-287` — feed source 選択と、`use` が feed 処理を迂回する分岐
- `strata_cli/update_cmd.py:378-394` — engine 特定・切替と成功出力
- `strata_control/engine_library.py:180-211, 225-289` — installed engine の列挙、候補解決、Qwen/DeepSeek の切替
- `strata_control/updater.py:1303-1352` — active engine の選択/pin と状態更新

調査範囲は記載した checkout の Terminal CLI parser、engine library、engine 切替実装です。CLI の help 表示や Release 配布物は確認していません。
