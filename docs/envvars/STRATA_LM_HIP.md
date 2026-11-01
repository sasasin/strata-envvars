# `STRATA_LM_HIP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

HIP build で layer-major prefill の実行を許可する追加 opt-in です。これだけでは layer-major prefill は選択されません。先に `STRATA_PREFILL_LAYER_MAJOR` が layer-major を有効にし、そのうえでこの変数が有効と判定されたとき、HIP build の `lm_prepare()` は NVIDIA CUDA 専用としていた拒否を通過します。未設定または無効値なら prompt は通常の chunk-major 経路を使います。

`tools/par/recon3.py` は HIP 用 arm の引数として `--env STRATA_LM_HIP=1` を `armrun.py` に渡しますが、これは測定 harness の設定です。同ファイル内に Strata engine の読み取り処理はありません。

## 値と判定

HIP build（`STRATA_USE_HIP` または `STRATA_HIP_GFX906` 定義時）でのみ環境から読み取られます。`std::getenv()` の結果があり、先頭文字が `'1'` の場合だけ有効です。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（値は設定されているが `v[0]` は `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, `-1`, ` 1`, `off`, その他先頭文字が `1` でない値 | 無効 |

判定結果は `lm_prepare()` 内の `static const bool` に保存されます。最初に関数へ到達した時点の値がそのプロセスで使われ、以後の環境変更は再評価されません。HIP 条件のない build ではこの名前を読むコードはコンパイルされません。

根拠: `src/prefill/prefill.cpp:5955-5968`。

## 有効になる条件

通常の単一 prompt の layer-major 経路では、両方の環境条件が必要です。

- `STRATA_PREFILL_LAYER_MAJOR` が空でない文字列で `std::atoi()` の結果が 0 以外であること。HIP build の既定値は OFF です。`STRATA_DEFAULTS=026` も既定を OFF にしますが、明示した `STRATA_PREFILL_LAYER_MAJOR` は既定より優先されます (`include/strata/core/sm120_series.hpp:107-120`)。
- `STRATA_LM_HIP` が先頭文字 `1` であること。これを満たさない場合、`lm_prepare()` は理由 `layer-major prefill has only been run on NVIDIA CUDA` を返して準備を拒否します。

さらに、layer-major の実行には prompt ごとの適用条件があります。layer hand-off 中、peer GPU、分割 stage の PLE 配置不整合、画像 prompt、DFlash2 prompt taps、`STRATA_KVA` 有効、chunk 境界で yield する batch read、`--prefill-pipe` による chunk 指定、ビルド済みの expert-nibble 経路での nibble expert、routing/row debug dump、モデルの expert plan や必要 buffer の不足、対応しない expert format / fused layout、短すぎる prompt、super-chunk 用 VRAM 不足などがあると準備は拒否されます (`src/prefill/prefill.cpp:5971-6044`)。したがって両環境変数が有効でも、すべての prompt でこの経路になるわけではありません。

複数 prompt の co-read は `run_multi()` から `lm_prepare_chain()` を直接試す経路です。ここでも `STRATA_LM_HIP` の判定を通ります。HIP opt-in がなく準備に失敗すると `prefill: multi-prompt read declined: ...` を返し、batch 呼び出し元は co-read を記録して通常の `sp.run()` に切り替えます (`src/prefill/prefill.cpp:6188-6206`, `src/program/generate.cpp:15214-15224`)。

## 実行時の詳細

layer-major prefill は super-chunk 単位で layer ごとに処理し、その super-chunk に含まれる routed experts を layer ごとにまとめて実行する経路です。通常の `Prefill::run()` は `STRATA_PREFILL_LAYER_MAJOR` の解決が true の場合に `lm_prepare_chain()` を試します。準備に成功すると `run_layer_major()` を実行し、失敗時は理由を stderr に出して `run_impl()` の chunk-major 経路へ進みます (`src/prefill/prefill.cpp:7222-7272`)。HIP build では `STRATA_LM_HIP` が無効だと、この準備失敗が通常の fallback につながります。

layer-major が既定で有効になった経路では `strata prefill: layer-major prefill is on for this layer split ...`、prompt ごとの準備失敗では `strata prefill: layer-major off for this prompt: <理由>` が stderr に出ます。HIP build は既定 OFF のため、明示的に layer-major を要求していない場合には、この通常経路で `STRATA_LM_HIP` の拒否ログは発生しません。co-read の拒否は呼び出し元が stderr に `strata batch: co-read of ... declined (...)` を出します (`src/prefill/prefill.cpp:7245-7269`, `src/program/generate.cpp:15218-15222`)。

資料 `docs/release-notes-0.2.7.md:20` は当時の Radeon では旧経路を使うと説明しています。HEAD のソースには gfx1201 を qualifying 中とするコメントがありますが (`src/prefill/prefill.cpp:5958-5965`)、この調査では build や GPU 実行をしていないため、特定の HIP GPU での実行可否・品質・性能は確認していません。

## 根拠

- `src/prefill/prefill.cpp:5955-5968` — HIP build に限る環境読み取り、先頭文字判定、無効時の拒否理由。
- `include/strata/core/sm120_series.hpp:107-120` — layer-major の既定条件と `STRATA_PREFILL_LAYER_MAJOR` の値判定。
- `src/prefill/prefill.cpp:5971-6044` — `lm_prepare()` が見る適用条件と資源条件。
- `src/prefill/prefill.cpp:6117-6169,6188-6206` — stage chain の準備、multi-prompt の拒否経路。
- `src/prefill/prefill.cpp:7222-7272` — 通常 prompt の layer-major 選択、ログ、chunk-major fallback。
- `src/program/generate.cpp:15214-15224` — co-read 拒否後の通常 prompt read fallback。
- `tools/par/recon3.py:35,39-44,48-57` — HIP 用測定 arm が `--env STRATA_LM_HIP=1` を子プロセスへ渡す箇所。
- `docs/release-notes-0.2.7.md:20` — Radeon での旧経路に関する release note。
