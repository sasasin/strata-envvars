# `strata` エンジンの `--resident-experts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 概要

`--resident-experts` は値を取らないフラグです。GPU の expert cache に載らない expert を起動時に RAM へコピーする resident RAM mode を有効にします。コマンド例:

```sh
strata generate --pack /path/to/model --expert-profile /path/to/profile.bin --resident-experts
```

`--expert-profile` にはモデルの layer/expert に対応する静的 profile を指定します。profile を読み込む処理は `src/program/generate.cpp:4415-4457` にあり、resident mode はこの profile の順位を使って RAM に保持する expert を選びます。上のパスは例示です。

## 値と既定値

- 引数値・短縮 alias はありません。parser がフラグを見つけると `mmap_experts`、`resident_cpu_experts`、`resident_pin`、`resident_soft` を有効にし、RAM headroom を4 GiBに設定します（`src/program/generate.cpp:2757-2765`）。help の説明も `src/program/generate.cpp:1066-1071` にあります。
- フラグを省略した場合、これらの状態は既定で無効です。内部の通常 headroom は8 GiBですが、このフラグを指定すると4 GiBへ変わります（`src/program/generate.cpp:536-549`）。
- このフラグ単独の値 validation はありません。`--expert-profile` が空、または `--mmap-experts` が無効のまま `--resident-cpu-experts` が有効なら、検証で stderr に要件を出して終了コード2になります。`--resident-experts` は mmap も同時に有効にしますが、静的 profile は別途必要です（`src/program/generate.cpp:3040-3046`）。

## 実行時の動作

起動時に expert source が GPU cache の補集合を計画し、profile の順位を渡して RAM resident copy を構築します。GPU cache 所有分や layer split / helper GPU cache 所有分はコピー対象から除かれます（`src/program/generate.cpp:8059-8065`, `8123-8134`, `8203-8205`; 実装 `src/core/expert_source.cpp:3477-3496`）。resident copy が使われると expert の file bytes を RAM から使い、通常の mmap file cache 経由と同じ bytes・配置なので、コメント上は同じ配置で同じ回答になるとされています（`src/program/generate.cpp:8060-8065`）。

フラグは `--mmap-experts` を含意するため `--shared-expert-arena` とは併用できず、検証エラー（終了コード2）になります（`src/program/generate.cpp:3040-3042`）。`--resident-cpu-experts` も含意します。RAM copy は page lock を試み、page lock の可否にかかわらず起動ログに `page-locked`、`locked`、`pageable` のいずれかが表示されます（`src/program/generate.cpp:8264-8270`）。

## 適用条件と相互作用

- profile が必須です。`--expert-profile` 自体の読込失敗は別途 profile reader のエラー経路を通ります（`src/program/generate.cpp:4415-4457`）。
- `STRATA_RESIDENT_PIN=0` を設定すると page-lock 要求を無効にします。`STRATA_RESIDENT_HEADROOM_GIB` に `atof` で0以上と解釈される値を設定すると、headroom をその GiB 値へ変更します（`src/program/generate.cpp:2760-2765`）。不正文字列の扱いは `atof` に従うため、厳密な数値形式 validation はありません。
- RAM に全補集合を確保できない場合、このフラグが有効にする soft fallback は profile 上位のうち確保できる分だけ RAM に残し、残りを model folder の mmap/file cache 経由で読みます。1件も保持できない場合は resident copy を使わず mmap 読みに戻ります（`src/program/generate.cpp:8204-8221`, `8271-8274`; `src/core/expert_source.cpp:3558-3560`）。
- prompt path が GPU cache slot を借りる構成では、その slot の expert も RAM copy に含める計画が行われます。実際に保持できる量は headroom と available RAM に制約されます（`src/program/generate.cpp:8112-8117`, `8204-8219`; `src/core/expert_source.cpp:3631-3645`）。
- `--adapt-every` と `--adapt-swaps` を有効にした構成では、resident RAM copy と GPU cache の間で expert を交換できます。成功時ログは adaptive swaps の有無も示します（`src/program/generate.cpp:8264-8270`; 用途説明 `src/program/generate.cpp:8066-8071`）。

## 出力と失敗

成功時は stderr に RAM 上の expert 量、page-lock 状態、GPU cache の resident 数、adaptive swap 状態を表示します（`src/program/generate.cpp:8264-8270`）。soft fallback 時は全量が収まらなかった理由と、残りを model folder から mmap 読みする旨を `WARNING` として出します（`src/program/generate.cpp:8271-8274`）。

resident copy 作成に失敗して soft fallback も成立しない場合は `CPU expert residency: <理由>` を stderr に出して終了コード1になります。GPU cache が完全に fill されていない、mapped source が開いていない、同期失敗、メモリ不足などは `pin_cache_complement` が失敗理由を返す経路です（`src/program/generate.cpp:8204-8221`, `8271-8284`; `src/core/expert_source.cpp:3463-3475`, `3611-3628`）。

## 根拠と調査範囲

- 索引上の scope は CMake 生成のネイティブ推論 engine `strata` の `src/program/generate.cpp` parser です（`docs/cli/README.md:1128-1134`, option link `docs/cli/README.md:1269-1271`）。
- parser/help/state: `src/program/generate.cpp:536-549`, `1066-1071`, `2754-2776`。
- validation/profile: `src/program/generate.cpp:3040-3046`, `4415-4457`。
- resident copy と結果: `src/program/generate.cpp:8059-8071`, `8112-8134`, `8203-8284`。
- 補集合計画、headroom 検査、profile 順位付け: `src/core/expert_source.cpp:3457-3496`, `3512-3564`, `3600-3645`。

記述は上記 commit の checkout に含まれる parser と使用箇所に基づきます。Release 配布バイナリ、全 OS / driver の page-lock 実動作、各 pack での必要 RAM 量はこの調査では実行・測定していません。
