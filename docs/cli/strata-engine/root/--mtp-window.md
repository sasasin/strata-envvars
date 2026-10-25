# `--mtp-window`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--mtp-window` |
| 別名 | なし |
| 値 | 整数。MTP draft layer が参照する過去セル数の上限 |

## 役割

MTP draft layer の attention が参照する過去セルの範囲を制限します。値は通常の推論エンジン parser で `int64_t` に変換され、MTP drafter のロード処理へ渡されます。既定値は `32768` です（`src/program/generate.cpp:681,2624`）。

## 使い方

```sh
strata --native model.gguf --mtp ./mtp-runtime --spec 4 --mtp-window 16384
```

MTP drafter を使う実行では `--mtp` と `--spec 2` 以上を指定します。`--mtp-window` 単独では drafter はロードされず、この値による MTP 動作もありません（`src/program/generate.cpp:5455-5472`）。

## 値と既定値

- 未指定時は `32768` です（`src/program/generate.cpp:681`）。
- parser は次の引数を `std::atoll` で変換します。明示的な範囲検証や変換失敗検査はありません。したがって数値として変換できない文字列は `0` として扱われます（`src/program/generate.cpp:2418-2421,2624`）。
- 値 `0` は window 制限を無効にし、全セルを対象にします。負数も実装上は同じく window 制限なしとして扱われます。正数が session の `max_cells` 以上の場合も制限は設定されず、全セルが対象です（`src/core/mtp.cpp:341-345,372-374`）。
- 同じ option を複数回指定した場合、引数ループ内で値を順に代入するため最後の指定が残ります（`src/program/generate.cpp:2416-2421,2624`）。
- 値を省略すると `next()` が `--mtp-window needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

CUDA/HIP の `MtpDrafter::load()` は、`0 < window < max_cells` のときだけ `window_` に値を設定します。draft attention の各ステップではこの `window_` から window ID を生成し、その ID を使う attention 経路へ渡します。値が `0` 以下、または `max_cells` 以上なら window ID による制限を行いません（`src/core/mtp.cpp:341-345,371-374,1029-1034`; `src/kernels/cuda/verify_kernels.cu:1014-1017`）。

KV streaming が有効なとき、正の window が `max_cells` 未満なら draft layer の K/V ring は `window + 4 * max_t + 64` セル分として初期化されます。制限を使わない場合の ring 引数は `0` です。window に応じて attention scratch の容量も決まり、正の window は 64 セル単位に切り上げられます（`src/core/mtp.cpp:341-345,352-364,371-374`）。ネイティブ側の割り当てが失敗した場合、`MTP` の K/V state が収まらない旨を `err` に設定し、呼び出し元はメッセージを stderr に出して終了コード `1` で終了します。pinned RAM が不足する場合は警告を出し、全 K/V を VRAM に置く fallback を試します（`src/core/mtp.cpp:352-363`; `src/program/generate.cpp:5472`）。

## 適用条件と副作用

- `--mtp` が指定されていても `--spec < 2` なら、エンジンは `--mtp is ignored without --spec T (T >= 2)` を stderr に出して `--mtp` を無効化します。その場合 `--mtp-window` も実質的に使われません（`src/program/generate.cpp:5455-5459`）。
- `--batch-mtp` の slot drafter も同じ `o.mtp_window` を `load()` に渡します（`src/program/generate.cpp:5520-5529`）。
- Metal ビルドの `MtpDrafter::load()` は `window` を明示的に未使用として Metal engine の `mtp_load()` を呼びます。このソースでは Metal 側に `--mtp-window` が反映されることを確認できません（`src/core/mtp.cpp:251-258`）。
- Qwen3.6 はモデル family switch で別 parser に移ります。Qwen3.6 の通常実行 parser に `--mtp-window` はなく、未対応引数として usage を出し終了コード `2` になります。Qwen3.6 の `--serve` 経路では未対応 option を警告付きで無視し、値らしい次引数も読み飛ばします。この別 family の MTP は `--mtp N` 形式です（`src/program/generate.cpp:2393-2406`; `src/qwen35/q36_engine.cu:3767-3773,3782-3795`）。
- 組み込み usage/help には `--mtp-window` の項目がありません。parser には存在するため、help 出力だけではこの option を確認できません（`src/program/generate.cpp:935-948,2623-2625`）。

## 出力とエラー

parser で値が欠落した場合は終了コード `2`、未知の引数は `unknown argument: ...` と usage を stderr に出して終了コード `2` です（`src/program/generate.cpp:2418-2420,2787-2792`）。MTP の load に失敗した場合は `strata generate: <理由>` を stderr に出し、終了コード `1` です（`src/program/generate.cpp:5472`）。値の範囲だけを理由に拒否する validation は確認できません。

## 根拠

- parser・既定値・help: `src/program/generate.cpp:681,935-948,2416-2421,2623-2625`
- MTP の適用条件と load 呼び出し: `src/program/generate.cpp:5455-5473,5520-5529`
- window、ring、scratch の設定と attention での使用: `src/core/mtp.cpp:341-374,1029-1034,1424-1426`; `src/kernels/cuda/verify_kernels.cu:1014-1017`
- Qwen3.6 の別 parser: `src/program/generate.cpp:2393-2406`; `src/qwen35/q36_engine.cu:3767-3795`
