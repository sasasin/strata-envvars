# `--stage-timing`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--stage-timing` |
| 別名 | なし |
| 値 | 値を取らない boolean flag |

## 役割

層内の区間ごとに GPU event を使った時間を集計し、実行後にレポートするための診断 flag です。parser はこの flag を設定しますが、現行 checkout では event の開始・終了を記録する関数の呼び出し箇所を確認できません。そのため、ソースから計測値が区間別の実時間を表すとは確認できず、性能判断に使える計測結果としては扱えません（`engine/src/program/generate.cpp:848-850,10435-10463`; `engine/src/core/layer.cpp:1099-1110`; 「実行時の動作」参照）。

## 使い方

```sh
# 実行例。MODEL.strata と token ID は利用環境に合わせる。
strata generate --pack MODEL.strata --tokens "1,2,3" --no-capture --no-pool --stage-timing
```

`--stage-timing` は通常の captured graph 経路では拒否されます。`--no-capture` を付けると、別の検査で `--no-pool` も要求されます。後者は CPU expert pool を使わない GPU-only 経路を選ぶため、通常の pool あり生成と同じ条件の測定ではありません（`engine/src/program/generate.cpp:10435-10440,10479-10487,10557-10571`）。

## 値と既定値

- 値・別名はありません。`Options::stage_timing` の初期値は `false` で、引数が `--stage-timing` と一致すると `true` になります（CUDA: `engine/src/program/generate.cpp:850,3933`; SYCL: `engine/sycl/src/program/generate.cpp:534,1972`）。
- 重複指定を拒否する処理はなく、複数回指定しても同じ `true` の状態です。値を付けた `--stage-timing=true` は一致する parser 分岐がなく、unknown argument と usage を stderr に出して終了コード `2` になります（`engine/src/program/generate.cpp:3933,4268-4273`）。
- 未指定時は timing 初期化とレポートの分岐に入りません（`engine/src/program/generate.cpp:10435,25401`）。

## 実行時の動作

1. parser は flag を `o.stage_timing` に保存します。層の fused GR 経路はこの値が true の場合に無効化され、計測向けに別の kernel 構成が選ばれます（`engine/src/program/generate.cpp:3933,6112-6113`; SYCL: `engine/sycl/src/program/generate.cpp:1972,3227-3228`）。
2. CUDA 実装と SYCL 実装はいずれも `--no-capture` がなければ、stream capture 内の event record が落ちて正しい結果にならないとしてエラーを stderr に出し、終了コード `2` で拒否します。通過後は各 stage 名を登録します（CUDA: `engine/src/program/generate.cpp:10432-10464`; SYCL: `engine/sycl/src/program/generate.cpp:5886-5918`）。
3. `--no-capture` 実行では `session_token` が CPU expert pool hook を持たないため、`--no-pool` がなければ routed experts が欠落するとして stderr に理由を出し、終了コード `2` で拒否されます（`engine/src/program/generate.cpp:10557-10571`）。このため、実行例の組み合わせは通常の pool あり生成とは異なる経路です。
4. CUDA/SYCL の timing 実装は stage ごとの event 対を最大 64 層分確保し、完了後に層ごとの経過時間を合計して `per-stage GPU time`、層あたり時間、割合などを stderr に出す設計です（CUDA: `engine/src/core/layer.cpp:1068-1089,1110-1128`; SYCL: `engine/sycl/src/core/layer.cpp:1068-1097,1119-1144`）。通常の生成完了処理からこのレポート関数を呼びます（CUDA: `engine/src/program/generate.cpp:25401`; SYCL: `engine/sycl/src/program/generate.cpp:14379`）。

### 計測結果に関する確認制約

現行 checkout の `engine/` 全体で `stage_mark_begin` / `stage_mark_end` を検索すると、宣言・定義のみで、層処理からの呼び出し箇所は見つかりませんでした。レポート関数はその event 対から経過時間を読みますが、呼び出し側で値が記録されていることを確認できません（`engine/include/strata/core/layer.hpp:363-364`; CUDA 実装: `engine/src/core/layer.cpp:1099-1107,1110-1128`; SYCL 実装: `engine/sycl/src/core/layer.cpp:1106-1117,1119-1144`）。よって、ヘルプの「per-stage KERNEL-COUNT shares」という説明（CUDA: `engine/src/program/generate.cpp:1389-1390`; SYCL: `engine/sycl/src/program/generate.cpp:946-947`）を実装上の出力として裏付けられません。また、レポートはカーネル数を集計せず GPU 時間として表示するコードですが、その値が有効な計測値かはソースから確認できません。

同じヘルプは `--gpu-only-full` を先に実行するよう案内しますが、これは別の実行で GPU-only 基準を測る案内です。`--stage-timing` 自体は `--no-capture --no-pool` が必要なので、captured graph を使う GPU-only 計測と同一実行にはできません（`engine/src/program/generate.cpp:1390,1393-1394,10435-10440,10557-10571`）。

## 適用条件と副作用

- CUDA および SYCL のエンジン parser に登録されています。両方とも `--no-capture` が必須で、さらに no-capture 経路の一般検査により `--no-pool` も必要です（上記参照）。
- flag を有効にすると fused GR が無効になるため、通常経路と計算構成が変わります（`engine/src/program/generate.cpp:6112-6113`; SYCL: `engine/sycl/src/program/generate.cpp:3227-3228`）。
- timing 初期化では CUDA event または SYCL event を多数作成し、レポート前に device/queue の完了を待つ実装です（CUDA: `engine/src/core/layer.cpp:1080-1089,1110-1112`; SYCL: `engine/sycl/src/core/layer.cpp:1080-1097,1119-1121`）。
- `--no-capture --stage-timing` だけでは `--no-pool` の検査で拒否されます。`--stage-timing` と `--no-capture` の不整合は終了コード `2`、CUDA event 初期化が false を返す場合は `stage_timing_enable failed` を stderr に出し終了コード `1` です（`engine/src/program/generate.cpp:10435-10444,10566-10571`）。SYCL の event 作成時に例外が起きる場合は catch 内で例外情報を stderr に出し `std::exit(1)` します（`engine/sycl/src/core/layer.cpp:1080-1097`）。

## 出力とエラー

- 成功経路ではタイミング表を stderr に出すコードがあります。通常の token 出力・decode 統計は別途 stdout に出力され、レポート後も通常の処理が続きます。したがって、`--stage-timing` は測定後すぐに終了するモードではありません（CUDA: `engine/src/program/generate.cpp:25401-25415`; SYCL: `engine/sycl/src/program/generate.cpp:14379-14390`）。
- captured path との併用は stderr の説明と終了コード `2`、no-capture で pool を残した場合も stderr の説明と終了コード `2` で失敗します。未知の引数も stderr に unknown argument と usage を出して `2` です（`engine/src/program/generate.cpp:10435-10440,10566-10573,4268-4273`）。
- CUDA のレポートは event elapsed の取得失敗時にその値を合計へ加えず続行します（`engine/src/core/layer.cpp:1114-1118`）。ただし begin/end event の記録呼び出しが見つからないため、成功時に表示される値が何を表すか、また SYCL で profiling 情報取得が成功するかは、このソース調査では確定できません。

## 根拠

- `engine/src/program/generate.cpp:848-850,3933` — option state の既定値と parser。
- `engine/src/program/generate.cpp:10432-10464,10566-10571,25401` — capture 条件、stage 名登録、no-capture 時の pool 条件、実行後の report 呼び出し。
- `engine/src/program/generate.cpp:6112-6113` — timing 有効時に fused GR を使わない条件。
- `engine/src/core/layer.cpp:1061-1067,1080-1128` — event 計測の前提、初期化、report 出力。
- `engine/sycl/src/program/generate.cpp:532-534,1972,3227-3228,5886-5918,14379` と `engine/sycl/src/core/layer.cpp:1080-1144` — SYCL 側の対応実装。
- `engine/include/strata/core/layer.hpp:355-364` — timing API 宣言。checkout 内検索では `stage_mark_begin` / `stage_mark_end` の呼び出し箇所を確認できず、実際の区間記録は検証できませんでした。
