# `--draft-cap`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--draft-cap` |
| 別名 | なし |
| 値 | 整数 `N`。verify window の最大幅として使う。 |

## 役割

`--draft dflash2` が有効な実行で、DFlash2 の verify window 幅（`--spec`）に上限を設けます。正の値を指定するとカード別自動上限を置き換えます。値 `0` は自動判定に戻します。自動判定は HIP の gfx1151（Strix Halo / UMA）で 5、CUDA compute capability major 12 で 6、それ以外では上限なしです（`src/program/generate.cpp:5498-5503`, `include/strata/core/draft_cap.hpp:8-16`）。

## 使い方

```sh
strata --native /models/target.native --tokens 1,2,3 --mtp /models/mtp --spec 8 \
  --draft dflash2 --draft-model /models/dflash2.pack --draft-cap 5
```

`--draft dflash2` には `--mtp`、`--spec 2` 以上、native pack、`--draft-model PACK` が必要です。対応 build の単一 GPU CLI 実行が対象で、`--serve`、`--batch`、layer split では DFlash2 ではなく MTP にフォールバックします（`src/program/generate.cpp:5474-5479`）。

## 値と既定値

- parser は次の argv を `atoi` で整数化し、`max(0, 値)` を保存します。負数は 0 になり、数値として読めない文字列も `atoi` の結果 0 となって自動判定扱いです。専用の範囲検証や変換エラーはありません（`src/program/generate.cpp:2418-2420,2701`）。
- 値の省略は許されず、次の argv がなければ `--draft-cap needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。
- 既定値は 0（自動）です。複数回指定した場合、parser は各値を順に代入するため最後の値が残ります（`src/program/generate.cpp:2416-2420,2701`）。
- 正の値は `--spec` を増やしません。DFlash2 をロードでき、GPU 属性の取得に成功したとき、上限が現在の `--spec` より小さければ `--spec` をその値に下げます（`src/program/generate.cpp:5481-5503`）。

## 実行時の動作

DFlash2 の load に成功すると GPU 0 の属性を調べ、自動値または指定値 `N` を cap として選びます。cap が正で `--spec` がそれを超える場合、stderr に上限適用を通知し、その後の verifier 初期化へ変更後の `--spec` を渡します（`src/program/generate.cpp:5481-5503,16135-16141`）。`--suffix-draft` / `--lookup-chain` が先に `--spec` を拡張していても、DFlash2 の cap 判定はその後に行われるため、最終幅はこの cap 以下になります（`src/program/generate.cpp:3205-3218,5474-5503`）。

自動上限の実装では HIP gfx1151 を UMA として扱い、CUDA では `dp.major`（compute capability major）を使います。`dflash2_auto_cap` は UMA なら 5、CUDA major 12 なら 6、それ以外は 0（上限なし）を返します（`src/program/generate.cpp:5486-5498`, `include/strata/core/draft_cap.hpp:8-16`）。CUDA build では統合 GPU でもこの helper に `uma=false` を渡します（`src/program/generate.cpp:5486-5497`）。

## 適用条件と副作用

- 値を実際に適用するコードは `STRATA_HAVE_DFLASH2` build 条件の内側にあります。CMake は DFlash2 の drafter を CUDA / HIP build に含め、Metal / SYCL build では含めないと記しています（`src/program/generate.cpp:5447-5450,5474-5519`; `CMakeLists.txt:339-340`）。非対応 build ではこの parser 自体は値を受理しますが、cap を適用する処理はありません。
- `--draft dflash2` が未指定、MTP・native pack・draft pack が不足、複数 GPU / batch / serve / layer split で条件に合わない場合、DFlash2 を使わず MTP にフォールバックし、cap は使われません。DFlash2 pack load に失敗した場合も stderr に理由を出して MTP にフォールバックします（`src/program/generate.cpp:5474-5482,5510-5517`）。
- GPU 属性を取得できない場合、カード別 cap を決める分岐は実行されません（`src/program/generate.cpp:5486-5488`）。DFlash2 自体が load 後に verifier の tap、bind、prepare を使えない場合も stderr に理由を出して MTP にフォールバックします（`src/program/generate.cpp:16148-16165`）。
- このオプションが直接変更するのは実行時の `o.spec` です。ファイルや設定を変更する処理はありません（`src/program/generate.cpp:5498-5503`）。

## 出力とエラー

`--spec` が選択 cap を超えた場合、stderr に `windows capped at N tokens` と表示します。正の `--draft-cap` は自動値ではない旨も表示します（`src/program/generate.cpp:5498-5502`）。引数欠落時は前述のとおり終了コード 2 です。値の書式・上限に対する個別エラーはなく、未知のオプションは通常 parser の unknown argument 経路で usage を表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。

## 根拠

- `src/program/generate.cpp:792-796` — option state と既定値。
- `src/program/generate.cpp:949-952` — 同一 revision の CLI help 表示。
- `src/program/generate.cpp:2416-2420,2699-2701` — 共通値取得、parser、値変換。
- `src/program/generate.cpp:3205-3218,5474-5517,16135-16165` — `--spec` との順序、DFlash2 適用・fallback。
- `include/strata/core/draft_cap.hpp:8-16` — 自動 cap のカード判定。
- `CMakeLists.txt:339-340` — DFlash2 の build 条件。
