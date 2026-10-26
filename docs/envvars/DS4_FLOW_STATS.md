# `DS4_FLOW_STATS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

同梱の DeepSeek-V4.1 実行経路（`strata-dsv41`、ソース上の実行名は `maya-ds4`）で、ファイル内の MXFP4 expert を GPU にストリームする flow 経路の統計を stderr に出します。環境変数自体は経路を有効化せず、ログを追加するだけです。通常の推論エンジン全体に共通する設定ではありません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | この変数による統計ログは出さない。`--verbose` が指定されている場合は別途ログが出る |
| 設定あり（空文字を含む任意の値） | 統計ログ出力を有効にする（flow 対象 device がある場合） |

値の内容、数値、先頭文字は調べません。`std::getenv("DS4_FLOW_STATS") != nullptr` という設定有無の判定です。

## 有効になる条件

- `strata-dsv41` の `src/dsv41` 実装を使うこと。
- `Model::feed()` が chunk 経路を選び、`forward_chunks()` が完了すること。入力長、設定された chunk、`pick_path()`、全位置の logits が必要かどうかによって `feed()` は chunk 経路または window 経路を選びます。
- 出力対象となる GPU の `Chunk` で `c.flow` が有効なこと。初期化時、flow は `DS4_FLOW` が未設定、または `atoi(DS4_FLOW) != 0` の場合に候補となりますが、少なくとも対象 device の trunk layer が MXFP4 であることが必要です。tensor-parallel では `DS4_FLOW_TP` も非ゼロでなければ flow 対象になりません。

flow が有効な device がなければ、`DS4_FLOW_STATS` を設定してもログ行は出ません。`o.verbose` が有効なら同じ統計出力ブロックに入るため、この環境変数がなくてもログが出ます。

## 実行時の詳細

`forward_chunks()` 内の各 run が device worker の完了後、各 `Chunk` を調べます。`o.verbose` が有効か、`DS4_FLOW_STATS` が設定されている場合に、`c.flow` の有効な各 device について stderr に `ds4 prompt stream, CUDA%d: ...` の行を出します。run ごとに環境変数を読み直すため、static cache されません。

各行には、run の token 数と経過時間、ストリームした expert 数と内訳（ファイル、RAM、layer cache）、ファイルから読んだ量（direct/unbuffered と buffered/page cache）、算出した読み取り帯域、早期にキューした likely expert 数と未選択数、読み取り待ち時間が含まれます。layer-major cache を使った場合は、キャッシュから再利用した expert 数と cache の chunk 数・RAM 使用量も追記します。これらは `Chunk` に蓄積した run 単位のカウンタと `IoQueue` の byte counter の差分から作られ、ログ出力のために推論結果や経路を変更しません。

## 根拠

- `src/dsv41/ds4_model.cu:8385-8406` — 設定有無または `verbose` による出力条件、flow chunk ごとの stderr ログと項目。
- `src/dsv41/ds4_model.cu:524-613,7627-7633` — flow 状態、ログ用カウンタ、および各 run のカウンタ初期化・I/O byte counter 基準値。
- `src/dsv41/ds4_model.cu:2694-2737` — `DS4_FLOW` / `DS4_FLOW_TP` の判定、MXFP4 等の条件、flow 初期化。
- `src/dsv41/ds4_model.cu:8187-8192,8279-8318` — chunk 経路と device worker の完了後に統計を出す呼び出し構造。
- `src/dsv41/ds4_model.cu:9356-9367` — `Model::feed()` が chunk 経路または window 経路を選ぶ条件。
- `CMakeLists.txt:797-809` — `src/dsv41` を含む `strata-dsv41` ターゲット。
- `docs/DETAILS.md:1131-1132` — prompt の chunk 処理と expert streaming の一般説明。`DS4_FLOW_STATS` 固有の説明や測定値は確認できず、上記の挙動はソースから確認した。
