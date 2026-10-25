# `--prefill-pipe`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル parser） |
| オプション | `--prefill-pipe` |
| 別名 | なし |
| 値 | `R`: `atof` で変換される数値。0、1、または 1 より大きい値を想定 |

## 役割

layer split の Prefill で、複数の stage が同時に処理するチャンク長を計画します。`R > 1` は setup の `--calibrate` が測る、この PC の stage-chunk 固定費と token あたり費用の比 `b/a`（token 単位）を指定します。`R = 1` は同じチャンク数を保ったまま均等化する規則を使います。`R = 0` はこの計画を無効にします。値を省略したときの既定は `STRATA_PREFILL_PIPE`、それも未設定なら 0 です（`src/program/generate.cpp:635-638`, `src/prefill/prefill.cpp:2245-2258`, `include/strata/prefill/prefill.hpp:95-110`）。

## 使い方

```sh
strata --serve --layer-split 24 --split-device 1 --native /models/shard1.gguf --prefill 4096 --prefill-pipe 1
```

例は `--serve` の2 GPU layer split とネイティブ経路で、等分化規則を指定します。実際にはモデルに合う `--pack`、必要な PLE shard 等も指定してください。`--layer-split` は `--serve` が必要で、複数 GPU へ分割するときは split 境界ごとに GPU が必要です（`src/program/generate.cpp:2629-2638`, `src/program/generate.cpp:2981-3027`, `src/program/generate.cpp:856-858`, `src/program/generate.cpp:960-966`）。

## 値と既定値

- parser は値を `std::atof` で変換し、`std::max(0.0, ...)` を適用します。別名や重複指定の検査はなく、複数回なら最後の指定値が残ります（`src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2601`）。
- 正の値で `1` 以下は等分化規則として扱われます。したがって想定値 `1` のほか、0 より大きく 1 未満も同じ規則になります。`1` より大きい値は整数 token 数へ丸めて比として利用し、内部計算では最大 `1,048,576` に制限されます（`src/prefill/prefill.cpp:2262-2265`, `src/prefill/prefill.cpp:2270-2296`）。
- `0` と負値は 0 になります。`atof` が変換できない文字列も通常は 0 になり、専用の値形式エラーはありません。`nan` は `std::max` の結果 0 となります。正の無限大は parser では有限化されず、内部の token 比変換で上限に丸められます（`src/program/generate.cpp:2601`, `src/prefill/prefill.cpp:2262-2265`）。
- 値が欠けている場合は `--prefill-pipe needs a value` を stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。
- オプションを指定しない場合は `STRATA_PREFILL_PIPE` が参照され、空文字または未設定なら 0 です。CLI で明示的に `--prefill-pipe 0` を指定すると環境変数設定を上書きして無効化します（`src/program/generate.cpp:4497-4498`, `src/prefill/prefill.cpp:2248-2258`）。

## 実行時の動作

parser は値を `Options::prefill_pipe` に保存し、engine 初期化時、0以上のときに `Prefill::set_pipe` へ渡します。未指定時は setter を呼ばず、Prefill 側が環境変数を読む遅延既定値を使います（`src/program/generate.cpp:635-638`, `src/program/generate.cpp:4497-4498`, `src/prefill/prefill.cpp:2246-2260`）。

複数 stage があり、先頭 stage の Prefill 経路から計画するときだけ `pipeline_chunk` が働きます。stage が1つ、値が0以下、または後段 stage では通常のバッファ chunk が使われます。`R = 1` は現在の chunk 上限で決まる chunk 数を維持し、最終 chunk が `stream_all_min_tokens()` 以上のときだけ 256 token 境界にそろえます。`R > 1` は `b/a` の比を用い、buffer 上限内の候補を比較して、現状より推定コストが3%を超えて改善する場合に chunk を変更します（`src/prefill/prefill.cpp:2262-2296`, `src/prefill/prefill.cpp:2298-2307`）。

計画された chunk は prompt segment 全体に対して一度決められ、分割読み込み、BYIELD、中断後の再開でも同じ計画を再利用します。再開時に segment 境界・chunk・現在の pipe 設定が保存計画と合わない場合は再計画し、その旨を stderr に出します（`src/program/generate.cpp:13435-13466`, `src/program/generate.cpp:13469-13483`, `src/program/generate.cpp:12323-12324`, `src/program/generate.cpp:12334-12353`）。serve request の `pipe=` キーは request 単位の値として先に優先され、リクエストごとに未指定状態へ戻されます（`src/prefill/prefill.cpp:2247-2259`, `src/program/generate.cpp:12318`, `src/program/generate.cpp:12352`, `src/program/generate.cpp:12369`）。

`--prefill-pipe` 自体は Prefill buffer の容量を増やしません。chunk 上限は Prefill buffer の chunk として渡されます。Prefill 経路を有効にする `--prefill CHUNK` は `--native` が必要です（`src/program/generate.cpp:960-966`, `src/prefill/prefill.cpp:2303-2307`, `src/prefill/prefill.cpp:2637-2645`）。

## 適用条件と副作用

- help は「layer split」向けと説明し、layer split の CLI validation は `--serve` を要求します。実際に複数 stage へ分割された Prefill でなければ計画は適用されません（`src/program/generate.cpp:963-966`, `src/program/generate.cpp:2981-3027`, `src/prefill/prefill.cpp:2303-2307`）。
- 設定が変えるのは prompt の chunk 分割と stage 間の重なり方です。推定比 `b/a` は機材に依存し、ソースコメントも誤った比で性能が落ち得るとしています。実測なしに速度向上を保証しません（`src/prefill/prefill.cpp:2228-2244`）。
- chunked 計画の読み込みは stage 間の重なりを前提に CPU share を使わない処理になります（`src/prefill/prefill.cpp:2641-2645`）。ログ出力以外に、このオプション固有のファイル変更やネットワーク通信は確認できません。

## 出力とエラー

計画 chunk が通常の buffer chunk より小さい場合、stderr に `strata prefill: ... tokens in ...-token chunks over ... stages (--prefill-pipe ...)` の行を出力します（`src/prefill/prefill.cpp:2314-2320`, `src/program/generate.cpp:13463-13466`）。不明な引数は stderr に `unknown argument` と usage を出して終了コード 2 になります（`src/program/generate.cpp:2787-2793`）。parser 段階で不正な数値形式を拒否する経路はありません。

## 根拠

- parser の既定値・help 表示・値の変換: `src/program/generate.cpp:635-638`, `src/program/generate.cpp:963-966`, `src/program/generate.cpp:2418-2421`, `src/program/generate.cpp:2601`
- layer split の適用条件と `Prefill::set_pipe` 呼び出し: `src/program/generate.cpp:2981-3027`, `src/program/generate.cpp:4497-4498`
- 環境変数の優先順位、pipe 値の正規化、chunk 計画とログ: `src/prefill/prefill.cpp:2245-2320`, `include/strata/prefill/prefill.hpp:95-123`
- 読み込み計画の適用・再開: `src/program/generate.cpp:13435-13483`
- request 単位の pipe 値: `src/program/generate.cpp:12315-12324`, `src/program/generate.cpp:12334-12369`

調査は指定 commit のソース checkout に限定しました。実機での `--calibrate`、GPU 性能、各 backend における実測値は確認していません。
