# `STRATA_DUMP_MOE_INPUT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

バッチ prefill の MoE 層で、指定した層の expert 入力行と routing expert ID を一度だけバイナリファイルへ書き出す診断用フックです。`mmq_nvfp4_parity --real` は、この実データを使った製品計算の検査入力として利用します。生成結果やモデル設定を変えるための通常利用者向け設定ではありません。

## 値と判定

| `STRATA_DUMP_MOE_INPUT` | 動作 |
|---|---|
| 未設定 | 最初に判定した時点で無効。以後このプロセスでは設定しても有効にならない |
| 設定あり（空文字を含む） | 値を出力パスとして保持し、対象層で一度だけ保存を試みる。空文字では `fopen` が失敗する |
| その他 | 値全体をパスとして `fopen(path, "wb")` に渡す。既存ファイルは上書きモード |

パスは `static const char*` に初回実行時の `getenv()` 結果として保存されます。値を真偽値や数値として parse しません。対象層は別変数 `STRATA_DUMP_MOE_LAYER` で選びます。この変数は各判定時に読み直され、未設定なら文字列 `"0"`、設定時は `atoi` で変換します。したがって空文字や数値に変換できない文字列は 0、先頭の空白・符号と数字の後ろに続く文字は `atoi` の規則で扱われます。変換結果と現在の層番号 `l` が一致したときに保存を試みます。

## 有効になる条件

- `strata_prefill` が含まれる GPU ビルドであること。CMake は CUDA/HIP GPU 構成の中で `src/prefill/prefill.cpp` をライブラリに含めます。
- バッチ prefill が MoE 層のこの処理まで到達し、選択した層番号と一致すること。
- MoE の fused 経路 `fused_l` ではなく、その `else` 側の経路を通ること。このため、変数を設定しても fused 経路だけを使う実行では保存されません。

## 実行時の詳細

対象層で最初に条件が一致すると、関数内 static の `dumped_moe` を先に `true` にします。続いて GPU 上の `m.mixed` から `T × N` 個の float をホストへ非同期コピーし、compute stream を同期してからファイルを開きます。ファイルのバイト列は次の順です（ネイティブ表現、追加の magic/version はありません）。

1. `T`, `N`, `K` の3要素（各 `int64_t`）
2. `T × N` 個の `float` 入力行データ
3. `T × K` 個の `int32_t` expert ID（`ids_h`）

`T` はその chunk の token 行数、`N` は hidden 幅、`K` は token あたりの routing 数です。層番号は 0 始まりの `l` と照合されます。同じプロセスでは static フラグにより1回しか保存を試みず、複数の Prefill インスタンスや後続 chunk でも再試行しません。ファイルを開けなかった場合もエラーや警告を出さず、その試行で終了します。`fwrite` の戻り値も検査しないため、書き込み失敗をこのコードが報告することはありません。対象層の処理にはデバイスからのコピーと stream 同期が加わります。

## 根拠

- `src/prefill/prefill.cpp:3123-3125` — fused MoE でない側の host grouping 経路。
- `src/prefill/prefill.cpp:3361-3377` — 環境変数の取得、layer 判定、初回フラグ、device-to-host copy、同期、ファイル形式と書き込み。
- `CMakeLists.txt:603-624` — GPU 構成で `strata_prefill` に `prefill.cpp` を含め、実行ファイル `strata` にリンクする構成。
- `docs/NVFP4.md:157-164,192-196` — `mmq_nvfp4_parity --real` がこの dump を実データ入力に使う説明と、同文書に記載された測定表。測定値は同文書の条件に限られ、本変数自体の性能や結果を保証するものではありません。
