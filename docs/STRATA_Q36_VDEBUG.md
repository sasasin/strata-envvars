# `STRATA_Q36_VDEBUG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

Qwen3.6 専用エンジンで Q8_1 量子化結果の比較不一致が起きたとき、最初の不一致ブロックについて追加情報を stderr に出す診断用フックです。比較や通常の不一致報告を有効にする変数ではありません。比較本体は別の `STRATA_Q36_VERIFY` が設定されている場合に実行されます。

## 値と判定

値を parse せず、`std::getenv("STRATA_Q36_VDEBUG")` が null かどうかだけを確認します。unset なら追加診断を出さず、空文字を含め何か設定されていれば有効です。したがって `0`、`false`、空文字も有効値です。コマンドライン引数や設定ファイルによる上書きはありません。

| 状態 | 追加診断 |
|---|---|
| unset | 無効 |
| 設定あり（空文字を含む） | 比較不一致などの条件を満たす場合に有効 |

## 有効になる条件

- Qwen3.6 (`qwen35moe`) の専用エンジン経路が使われること。`strata` はモデルのアーキテクチャを見てこの経路へ切り替えます。
- `STRATA_Q36_VERIFY` が設定され、Q8_1 比較が行われること。この変数も値ではなく設定有無で判定されます。
- `verify_q8()` で今回の比較が不一致となり、同じ比較名 (`what`) の不一致数が2以下であること。

`verify_q8()` は、小さい decode バッチでの post-attention RMS 後、および条件を満たす小さい MoE 出力後に呼ばれます。比較は `fast_k` 経路の該当処理に限られます。`STRATA_Q36_VERIFY` が未設定なら `STRATA_Q36_VDEBUG` だけ設定しても比較も追加診断も行われません。

## 実行時の詳細

`STRATA_Q36_VDEBUG` は各 `verify_q8()` 呼び出しで読み直されるため、値はキャッシュされません。実際に出力するのは、Q8_1 の新旧画像を比較して不一致があった場合です。不一致ブロックの新旧 scale のビット列、quantized 値部分の一致状態、入力値から CPU 上で計算した butterfly sum とその half 値を1行にして stderr へ出します。ブロック走査は最初に見つけた不一致で止まります。同じ `what` について追加行を出すのは最大2回です。

出力文言は `VDEBUG block %zu: ds new %08x old %08x, qs bytes %s, cpu butterfly sum %.9g (half %04x)` です。変数 unset の場合でも、`STRATA_Q36_VERIFY` が設定されていて比較不一致があれば、通常の `strata-q36 VERIFY MISMATCH ...` は別途 stderr に出ます。`STRATA_Q36_VDEBUG` は計算結果、モデル出力、比較回数を変えず、追加の device-to-host コピーと CPU 側診断計算を行います。

## 根拠

- `src/qwen35/q36_engine.cu:1575-1594` — `STRATA_Q36_VERIFY` の設定有無、比較不一致カウント、通常の不一致ログ。
- `src/qwen35/q36_engine.cu:1631-1662` — Q8_1 比較後の `STRATA_Q36_VDEBUG` 判定、出力条件、ブロック診断処理。
- `src/qwen35/q36_engine.cu:1672-1690,1837-1857` — 検査経路と `verify_q8()` の呼び出し条件。
- `src/program/generate.cpp:2252-2267` — `qwen35moe` モデルを専用エンジンへ切り替える処理。
- `docs/QWEN36.md:130-134` — Qwen3.6 エンジンの decode 検証説明。性能・正確性の記載は資料にある測定内容であり、この調査で再測定していません。
