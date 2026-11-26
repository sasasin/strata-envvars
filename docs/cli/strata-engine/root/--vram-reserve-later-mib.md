# `strata`（Strata engine）`--vram-reserve-later-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジンのトップレベル引数） |
| オプション | `--vram-reserve-later-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。parser は `atoi` で変換し、独自の範囲検査をしない |

## 役割

レイヤー分割で使う後段 GPU の空き VRAM 見積もりに、先頭 GPU 用の予約量とは別の基本予約量を指定します。後段 GPU の分割配置や expert cache の利用可能量を見積もるための値で、既定では `--vram-reserve-mib` の値（未指定時 700 MiB）を引き継ぎます。先頭 GPU の予約量はこのオプションでは変わりません（`engine/src/program/generate.cpp:960-970, 6911-6922`）。

## 使い方

```sh
# 後段 GPU ごとに 1200 MiB を基本予約量として扱い、モデルを実行する
strata --pack /path/to/model --layer-split auto --vram-reserve-later-mib 1200
```

例の `--pack` と `--layer-split` は実行に必要なモデルと分割設定を示す文脈説明用の引数です。このオプション自体は値を1つ取ります。

## 値と既定値

- 既定値は内部値 `-1` です。後段 GPU で `-1` の場合は `--vram-reserve-mib` の値を使います。同オプションの既定値は 700 MiB です（`engine/src/program/generate.cpp:960-970`）。
- 数値は `std::atoi` で読み取られます。正の値だけに制限する validation はありません。0 は明示値として有効で、負数は後段計算の条件 `>= 0` を満たさないため、先頭 GPU 用の予約量へフォールバックします（`engine/src/program/generate.cpp:3997-3999, 5870, 6084, 6911-6914`）。
- 数字として解釈できない文字列は `atoi` の結果 0 になります。そのため独立した「不正な数値」エラーにはならず、0 MiB 指定と同様に扱われます（`engine/src/program/generate.cpp:3998-3999`）。
- 同じオプションを複数回指定した場合、引数ループで各値を順に代入するため最後の値が残ります（`engine/src/program/generate.cpp:3842-3847, 3998-3999`）。
- 値を省略すると parser の `next` が標準エラーに `--vram-reserve-later-mib needs a value` を出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846, 3998-3999`）。

## 実行時の動作

CUDA/HIP のレイヤー分割における配置探索では、後段 stage に限り、この値（非負値の場合）または `--vram-reserve-mib` を基本予約量にします。さらに prompt buffer、window、pipeline window、必要な drafter 等の予約分を加え、その合計を GPU の空き VRAM から差し引いて stage が expert cache に使える容量を見積もります。差し引き結果は 0 未満にならないようにされます（`engine/src/program/generate.cpp:6901-6922`; 計算式: `engine/include/strata/program/stage_reserve.hpp:36-56`）。したがって、この値を増やすと後段 GPU の cache に割り当て可能と見積もられる量は減り、小さくすると増えます。これは見積もり・配置計算への入力であり、指定量の VRAM を別途確保する処理ではありません。

同じ後段予約量は分割後の stage trimming の判定（`engine/src/program/generate.cpp:6074-6092`）や multi-GPU の見積もり表示にも使われます（同:5870-5872）。起動後、後段 CUDA GPU の空きが 512 MiB 未満なら stderr に低空き容量の注意を出し、目安値として「基本予約量 + 768 MiB - 現在の空き量」を表示します。さらに予約・prompt buffer・window 分を用いた計画値との比較を出す経路があります（同:16131-16163）。注意表示は値を自動変更しません。

SYCL 実装にも同名 parser があり、`atoi` で値を設定します。SYCL の stage 空き容量計算では後段 stage に限り非負の指定値を基本予約量に選び、window 等と合算して空き量から差し引きます（`engine/sycl/src/program/generate.cpp:634-636, 2015-2017, 3896-3918`）。

## 適用条件と副作用

- 主な効果はレイヤー分割時の後段 GPU の見積もりです。単一 GPU では後段 stage がなく、先頭 GPU の予約量を変更しません（`engine/src/program/generate.cpp:6911-6922`）。
- 予約量の見積もりには、CUDA/HIP の通常経路で後段 GPU 追加割当分（`late_alloc`）も加算される場合があります。これは `later` stage かつ `strata::qwen_defaults_026()` が false の条件です。オプション値そのものはこの加算分を置き換えません（`engine/src/program/generate.cpp:6908-6919`）。
- stage reserve の計算では後段 GPU の window 96 MiB、prompt buffer、pipeline 用 window、および配置条件に応じた drafter / DFlash2 の分を基本予約量に追加します（`engine/include/strata/program/stage_reserve.hpp:18-50`）。
- 起動後に空き VRAM が少ない場合、診断文は設定変更の目安を stderr に出しますが、このオプション値を書き換えたり、VRAM の確保を試みたりはしません（`engine/src/program/generate.cpp:16135-16163`）。
- ソース上の CUDA/HIP 低空き容量診断は後段 CUDA stage を走査します。別 backend やすべての失敗状態で同じ診断が出ることまでは確認できません。

## 出力とエラー

値の欠落時は上記のとおり stderr に不足を出して終了コード 2 となります。未知の引数は stderr に `unknown argument: ...` を出し、usage を表示して終了コード 2 です（`engine/src/program/generate.cpp:4268-4274`）。オプション値については数値範囲 validation がないため、範囲外を理由とする専用エラー経路は確認できません。

低空き容量の診断は stderr に出力され、CUDA stage の空き容量取得に失敗した場合はその stage の診断をスキップします（`engine/src/program/generate.cpp:16135-16147`）。実際の GPU allocation failure や他の起動失敗の挙動は、その発生箇所に依存し、このオプション固有のエラーには限定されません。

## 根拠

- `engine/src/program/generate.cpp:960-970` — 基本予約量の既定値と後段予約値の初期値。
- `engine/src/program/generate.cpp:3842-3847, 3997-3999` — 引数値の取得、整数変換、未指定値の失敗、および後段予約値の parser。
- `engine/src/program/generate.cpp:5870-5872, 6074-6092, 6901-6922` — 後段予約値を使う見積もり・stage trim 判定・cache room 計算。
- `engine/include/strata/program/stage_reserve.hpp:36-56` — 基本予約量に加算する項目と空き量計算。
- `engine/src/program/generate.cpp:16131-16163` — 起動後の後段 GPU 空き容量診断と比較。
- `engine/sycl/src/program/generate.cpp:634-636, 2015-2017, 3896-3918` — SYCL parser と stage の基本予約量計算。
- `engine/src/program/generate.cpp:4268-4274` — 未知引数の stderr・usage・終了コード。
