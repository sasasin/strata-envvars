# `--gpu-only-full`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root parser。usage 表記は `strata generate`） |
| オプション | `--gpu-only-full` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定は無効 |

## 役割

通常の生成処理を行わず、全 layer の captured `pre` / `post` graph と LM head を再生して、1 token 分の GPU work の計測値を表示します。`--graph-only` が `pre` graph だけを測るのに対し、このフラグは `post` graph と head も含む測定経路です（`src/program/generate.cpp:974-977,7315-7325`）。

## 使い方

```sh
strata generate --pack ./model --tokens "1,2,3" --gpu-only-full
```

`--pack` と token 入力はエンジンの基本構文に合わせた例です。token ID は手元のモデルに対応する値を指定してください。オプション自体には引数を付けません（`src/program/generate.cpp:806-812,2508-2510`）。

## 値と既定値

- `Options::gpu_only_full` の初期値は `false` で、parser はこの文字列を受け取ると `true` にします。値、数値範囲、別名はありません（`src/program/generate.cpp:517,2508-2510`）。
- 同じフラグを複数回指定しても有効化されるだけです。フラグの後ろにオプションとして解釈できない余分な値を置くと、通常の未知引数として usage を表示して終了コード `2` になります（`src/program/generate.cpp:2416-2423,2508-2510,2787-2792`）。

## 実行時の動作

- エンジンの通常の起動・モデル準備と graph capture を経てから測定分岐に入ります。graph capture は `--no-capture` でなく、かつ native pack でない場合に行われます（`src/program/generate.cpp:6952-6963`）。
- 計測時は doorbell を reset し、layer graph replay と LM head の実行を warm-up 1回と計測20回行います。各再生のあと stream を同期し、layer と head を別々に平均したうえで合計時間、ms/token、GPU work 換算の tok/s、layer 数、1 layer あたりの時間、LM head の時間を stdout に表示します（`src/program/generate.cpp:7325-7364`）。
- `session_replay_full` は各 layer の `pre` graph の直後に対応する `post` graph を同じ stream で launch します（`src/core/session.cpp:307-329`）。この計測分岐はその後 `return 0` するため、通常の token 生成ループへは進みません（`src/program/generate.cpp:7364-7367`）。
- `--serve` と同時に指定しても、測定分岐が server protocol の初期化より前に戻るため server は起動しません（`src/program/generate.cpp:7325-7367,8354-8359`）。
- 測定対象は GPU graph と head の実行時間です。CPU expert pool は呼び出さず、通常ループの PLE token lookup、embedding、logits 読み戻し、sampler も測定しません。そのため通常の生成全体の token latency や throughput を表す値ではありません（`src/program/generate.cpp:6928-6936,7323-7325,7483-7487`）。

## 適用条件と副作用

- `--layer-split` により複数 GPU の layer split が有効な場合は拒否されます。全 layer を単一 session で replay できないためで、stderr に理由と回避方法を出し、終了コード `2` で終了します（`src/program/generate.cpp:3386-3392`）。
- `--native-flash-attn-short` と併用すると、通常 decode loop での status validation が必要として拒否され、終了コード `2` になります（`src/program/generate.cpp:3382-3384`）。
- `--no-capture` は graph capture を省略します。単独では `--no-pool` も必要として早期に終了コード `2` になります。両方を指定した場合はその検査を通りますが graph がないため、測定時の `session_replay_full` が「post graphs が capture されていない」エラーになり、終了コード `1` で終了します（`src/program/generate.cpp:6952-6963,6965-6979,7331-7334`; `src/core/session.cpp:307-311`）。
- native pack も layer graph capture の対象外です。このフラグの測定分岐で `session_replay_full` を呼ぶと同じ未 capture エラー経路になります（`src/program/generate.cpp:6952-6963,7331-7334`; `src/core/session.cpp:307-311`）。
- Qwen3.6-35B 系は parser 前に family 専用実装へ委譲されます。この文書の適用範囲は通常の `src/program/generate.cpp` parser です（`src/program/generate.cpp:2393-2407`）。
- `--gpu-stages` や `--graph-only` も計測専用の早期 return 経路で、両方を重ねた場合は先に評価される計測分岐が本フラグの分岐に到達する前に戻ります（`src/program/generate.cpp:7136-7138,7277-7285,7313-7325`）。
- 本フラグの測定分岐は GPU 上で graph と head を繰り返し実行し、stderr/stdout に診断・計測出力を行います。分岐自体にはファイル出力処理はありません。起動時のモデル読み込みや GPU メモリ確保など、通常の engine 初期化による作用は別途あります。

## 出力とエラー

- 成功時は `GPU floor pre+post+head ... ms per token` に続いて GPU work 換算 tok/s、layer 合計、per-layer、LM head の計測値を stdout に出し、終了コード `0` で戻ります（`src/program/generate.cpp:7358-7364`）。
- graph replay の失敗は stderr に `session_replay_full: ...`、layer stream 同期の失敗は `gpu-only-full layers faulted: ...`、head 実行の失敗は `gpu-only-full lm_head: ...`、head 同期の失敗は `gpu-only-full head faulted: ...` を出し、いずれも終了コード `1` です（`src/program/generate.cpp:7331-7349`）。未 capture graph の詳細エラーは `src/core/session.cpp:309-311` を参照してください。
- この調査では同一 revision の既存 CLI help／バイナリは実行していません。help の記載と parser はソース上で照合しました。GPU/backend ごとの実測値や release 配布物の挙動は確認していません。

## 根拠

- `src/program/generate.cpp:513-517` — graph 計測フラグと `gpu_only_full` の既定値。
- `src/program/generate.cpp:806-812,972-977` — usage と help にある構文・オプション説明。
- `src/program/generate.cpp:2416-2423,2508-2510,2787-2792` — parser と未知引数の失敗経路。
- `src/program/generate.cpp:3382-3392` — `--native-flash-attn-short`、layer split との validation。
- `src/program/generate.cpp:6952-6979` — graph capture 条件と `--no-capture` の検査。
- `src/program/generate.cpp:7136-7138,7277-7285,7313-7367` — 先行する計測分岐、full 計測、出力と通常ループへの非到達。
- `src/program/generate.cpp:7483-7487` — GPU floor の測定範囲と通常 token loop で行う処理との差。
- `src/core/session.cpp:307-329` — full graph replay の capture 前提と `pre` / `post` graph の順序。
