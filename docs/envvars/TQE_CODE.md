# `TQE_CODE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`TQE_CODE` は `tools/dsv41_lab` の trellis GEMV 実験用に、ホスト側エミュレータが使用する計算型コードブックを選ぶ環境変数です。確認できた値判定による計算型選択は `wmma_emu_test` に限られ、通常の Strata 実行ファイルや `tools/trellis/tqenc.cpp` がこの環境変数を読む実装は確認できませんでした。`computed_codes.hpp` のコメントには tqenc encoder から読むとありますが、対象ソース全体の検索では encoder 側の読み取りは見つかりません。

## 値と判定

`wmma_emu_test` は `getenv("TQE_CODE")` を `tqcode::kind_of()` に渡します。値は大文字小文字を区別した文字列全体の完全一致で判定されます。

| 環境変数の状態・値 | `kind_of()` の結果 | `wmma_emu_test` の動作 |
|---|---|---|
| 未設定 | `kNone` | table codebook 経路で実行 |
| 空文字 | `kNone` | 変数が設定済みのため未対応値として扱い、終了コード 2 |
| `3single` | `k3single` | 計算型 `3single` 経路で実行 |
| `1mad`, `3inst`, `3sum` | それぞれの Kind | このテストでは未対応値として扱い、終了コード 2 |
| 上記以外（例: `0`, `3Single`, `3single `） | `kNone` | 変数が設定済みなので未対応値として扱い、終了コード 2 |

このため「未知の値が `kNone`」だけでは table 経路になりません。呼び出し側は環境変数が設定済みかを別に確認し、未設定なら table、空文字を含め設定済みかつ `3single` 以外なら `only TQE_CODE=3single is wired here` を標準出力に出して終了します。

## 有効になる条件

- `wmma_emu_test` を実行したときだけ、`3single` の値が選択動作を変えます。このツールはホストのみで実行でき、GPU は不要です。
- `tools/dsv41_lab/tqk_lab.cu` は値の内容を解析せず、設定有無だけで検証の失敗条件を一部緩和します。具体的には CUDA dequant の不一致を失敗に数えず、GPU と CPU GEMV の差の閾値判定も無効にします。したがって空文字や未知文字列も「設定済み」としてこの差分に影響します。
- `code_sqnr` は変数値を結果表示に使うだけで、そこで参照されるコードには `getenv()` を使った処理選択がありません。
- 設定値による通常の Strata エンジンの挙動変更は確認できません。

## 実行時の詳細

`wmma_emu_test` は起動時に環境を読みます。`3single` の場合は trellis state から2つの計算語を作る `step_3single` を GEMV エミュレータへ渡し、未設定時は出荷済み table codebook を使う `step_table` を渡します。環境変数を後から変更して再評価する処理はありません。

`code_sqnr` は encoder による符号化・復号後の SQNR を計算し、表示ラベルとして `TQE_CODE` の文字列を出します。ソース内にはこのツール自身によるコードブック切替がありません。そのため、値が実験条件に影響するというコメントと、当該ファイルで直接確認できる環境変数の効果（表示）を区別しました。

## 根拠

- `tools/dsv41_lab/wmma_emu_test.cpp:28-30` — 値判定、未対応値のメッセージと終了コード。
- `tools/dsv41_lab/wmma_emu_test.cpp:15-26, 33-35` — table / `3single` の関数と選択後のテスト経路。
- `tools/dsv41_lab/computed_codes.hpp:41-50` — 完全一致で認識する名前。未設定・空文字・未知文字列は `kNone`。
- `tools/dsv41_lab/tqk_lab.cu:170-174, 217-223` — 環境変数の設定有無で変わる検証失敗条件。
- `tools/dsv41_lab/code_sqnr.cpp:1-2, 31-32` — コメント上の想定と、実際の結果表示での読み取り。
- `tools/dsv41_lab/hip/README.md:14` — `wmma_emu_test` を `TQE_CODE=3single` 付きでも実行する手順。
