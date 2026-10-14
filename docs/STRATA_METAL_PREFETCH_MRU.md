# `STRATA_METAL_PREFETCH_MRU`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

macOS Metal エンジンの SSD streaming 経路で、予測 read-ahead によって読み込む expert slot を LRU の前端または後端に置きます。これは read-ahead の有効化や件数を決める設定ではありません。read-ahead の深さは `STRATA_METAL_PREFETCH` が決めます。

## 値と判定

`ExpertStream::open()` が `env_int("STRATA_METAL_PREFETCH_MRU", big ? 0 : 1)` を評価します。共通 helper は、変数が未設定または空文字なら既定値を使い、それ以外は `std::atoi()` の結果を使います。したがって文字列全体の数値検証はせず、数値変換できない先頭なら通常 `0`、数値に続く文字は無視されます（例: `1junk` は 1）。最終判定は `!= 0` です。

| 値 | 挙動 |
|---|---|
| 未設定または空文字 | expert サイズが大きい場合 `0`、それ以外 `1` |
| `0` または `0junk` | read-ahead slot を LRU 後端へ置く |
| 非ゼロの `atoi` 結果（例: `1`, `-1`, `2tail`） | read-ahead slot を LRU 前端へ置く |
| 数字に変換できない文字列（例: `true`） | `atoi()` が 0 を返すため LRU 後端へ置く |

「大きい」判定は、48 層分の gate/up/down expert サイズの合計を 48 で割った値が 1,500,000 byte を超えることです。閾値ちょうどは大きい側には入りません。

## 有効になる条件

この設定を読むのは Metal エンジンの `ExpertStream` です。`ExpertStream::wanted()` が streaming を選び `Window` がその経路を作った場合に限られます。streaming は `STRATA_METAL_STREAM=1` で要求でき、未指定などの場合はモデルの mapped weights と作業領域が resident footprint cap に収まるかで自動判定されます。

さらに read-ahead が実際に走るには decode 経路で予測 logits があり、`STRATA_METAL_PREFETCH` から得た件数が正である必要があります。後者の既定件数は大きい expert で 6、それ以外で 10 です。`STRATA_METAL_PREFETCH=0` などで `prefetch_` が false なら、この変数を設定しても read-ahead の LRU 配置には作用しません。prompt chunk の経路では `ahead()` を呼ばず、次層の未常駐 expert を別処理で後端に読み込みます。

## 実行時の詳細

`open()` 時に `pre_mru_` へ保存されるため、その `ExpertStream` の存続中は環境変数を変更しても再評価されません。decode の `at_layer()` は次層の予測上位 expert を `ahead()` に渡します。既に resident の expert は前端へ移動し、新規 read-ahead slot は `pre_mru_` が真なら前端、偽なら後端へ移動します。LRU の victim 選択は後端から探すため、前端配置は read-ahead slot を相対的に残しやすくし、後端配置は先に追い出されやすくします。slot の状態や現在の使用 pin によって victim に選べないこともあります。

この環境変数専用のログはありません。streaming の統計ログには read-ahead の件数などが出ますが、MRU 設定値は表示しません。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: unset/空文字時の既定値と `atoi()` 変換。
- `metal/src/engine/stream.cpp:33-48`: Metal streaming の明示指定と resident footprint による自動判定。
- `metal/src/engine/window.cpp:427-430`: streaming 選択後に `ExpertStream` を生成。
- `metal/src/engine/stream.cpp:149-163`: read-ahead 件数、モデルごとの `big` 判定、`pre_mru_` の初期化。
- `metal/src/engine/stream.cpp:253-267`: LRU 後端からの victim 選択。
- `metal/src/engine/stream.cpp:572-612,614-711`: 予測 expert の先読み、LRU 配置、および decode/prompt の経路差。
- `metal/src/engine/stream.h:119-120`: `pre_mru_` の状態。
- `docs/MAC.md:139`: M4 の記載では read-ahead 深さ・I/O thread 数・eviction order の各変更は decode を 3% 未満動かしたとあるが、ここでは `STRATA_METAL_PREFETCH_MRU` 単独の値ごとの比較条件や測定値は示されていない。
