# `strata --no-capture`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root 引数） |
| オプション | `--no-capture` |
| 別名 | なし |
| 値 | 取らない boolean flag。`--no-capture` を指定すると有効 |

## 役割

通常の token-by-token 生成経路で、層の実行を CUDA graph の capture/replay から、層を順に直接呼び出す経路へ切り替える。これは実行経路を選ぶフラグであり、CPU expert pool を保ったまま切り替えることはできない。`--no-pool` と併用した GPU-only の測定・診断用途に限られ、ルーティングされた expert を含む通常の推論結果を得るための指定ではない。`engine/src` と `engine/sycl/src` の parser に同じ flag と pool／dump 制約がある（`engine/src/program/generate.cpp:845-846,10557-10586`; `engine/sycl/src/program/generate.cpp:529-530,5970-6000`）。

## 使い方

```sh
# GPU-only の測定・診断例。CPU expert pool を使わず、通常の完全な推論出力を得る用途ではない。
strata --pack MODEL.strata --tokens 1,2 --no-capture --no-pool
```

`--pack` と `--tokens` は実行に必要な入力例であり、モデルと token ID は手元の環境に合わせる。`--no-capture` 自体には値を付けない（`engine/src/program/generate.cpp:3842-3853,3930`）。

## 値と既定値

値・別名・数値範囲はない。`Options::no_capture` の初期値は `false` で、parser が引数と完全一致したとき `true` にする。重複指定を拒否する分岐はなく、複数回指定しても同じ状態になる。`--no-capture=true` のような値付き表記はこの parser の分岐に一致せず、unknown argument として exit code 2 になる（`engine/src/program/generate.cpp:845,3930,3980-3984,4269-4272`）。

## 実行時の動作

通常の token-by-token 生成では、フラグなしなら session graph を capture し（native pack の場合を除く）、各 token で captured token graph または `session_loop` を使う。指定時は session graph と token graph の capture を抑止し、各 token で `session_token` を呼ぶ。`session_token` は全層を順番に走査し、各層について `block_layer` を直接呼ぶ。`--sync-every-layer` も指定した場合は各層の後に stream 同期を行う。SYCL 実装にも同じ通常生成経路の分岐がある（`engine/src/program/generate.cpp:10544-10555,10999-11000,24296-24314`; `engine/src/core/session.cpp:801-842`; `engine/sycl/src/program/generate.cpp:5957-5968,13504-13518`; `engine/sycl/src/core/session.cpp:1148-1188`）。

`session_token` には CPU expert pool の hook がない。そのため `--no-capture` 単独では routed experts が計算されない実行になる。parser 後のチェックで `--no-pool` がなければ stderr に理由を出して exit code 2 で拒否する。両方を指定するとこの拒否は避けられるが、CPU expert pool は無効であり、GPU-only floor の測定・診断として扱う（`engine/src/program/generate.cpp:846,10557-10571,10479-10484`）。

## 適用条件と副作用

- `--dump-layers` とは併用できない。これは `session_loop` が埋める staging buffer を書き出す機能で、`session_token` はその buffer を埋めないため、指定すると stderr に理由を出して exit code 2 で拒否する（`engine/src/program/generate.cpp:10573-10580`）。
- `--dump-halves` とは併用できない。half の記録は layer graph に capture されるため、直接実行経路では記録されず、指定すると exit code 2 で拒否する（`engine/src/program/generate.cpp:10582-10586`）。
- `--stage-timing` は逆に `--no-capture` を必要とする。`--stage-timing` だけを指定すると capture 内の CUDA event が記録されない理由を stderr に出して exit code 2 で拒否する。`--no-capture --stage-timing` の組合せでは timing 初期化を行い、初期化に失敗すると `stage_timing_enable failed` を stderr に出して exit code 1 になる（`engine/src/program/generate.cpp:10432-10445`）。
- フラグ自体によるファイル出力や設定ファイル変更は確認できない。層の実行経路を変え、`--no-pool` との併用時には routed experts を含まない GPU-only 経路になる。
- `--serve` との組合せを parser が専用に拒否する処理は確認できなかった。直接 `session_token` を呼ぶ箇所は通常の token loop にあり、serve の要求処理は別経路であるため、この調査では `--serve` 時の効果を通常生成と同じとは断定しない（`engine/src/program/generate.cpp:24296-24314`）。

## 出力とエラー

`--no-capture` 単独を受理したときに専用の表示はない。主な拒否・失敗経路は次のとおり。

| 条件 | 確認できる出力・終了 |
| --- | --- |
| `--no-pool` なし | `strata generate: --no-capture runs ...` を stderr に出し、exit code 2 |
| `--dump-layers` または `--dump-halves` と併用 | 各組合せの理由を stderr に出し、exit code 2 |
| `session_token` / 層の実行が失敗 | `session_token: <層番号とエラー>` を stderr に出し、exit code 1 |

これらの分岐と表示は `engine/src/program/generate.cpp:10566-10586,24296-24301` にある。その他の起動・GPU エラーは個別の初期化・実行処理が返すため、このオプション固有の失敗とは区別する。

## 根拠

- `engine/src/program/generate.cpp:845-849` — flag の既定値と隣接する `--no-pool`／`--stage-timing` の関係。
- `engine/src/program/generate.cpp:1289,3930` — help 表記と parser 登録。`engine/src/program/generate.cpp:3980-3984,4269-4272` は未知引数の扱い。
- `engine/src/program/generate.cpp:10544-10555,10999-11000` — graph capture と token graph capture の抑止条件。
- `engine/src/program/generate.cpp:10557-10586,10432-10445` — `--no-pool` 必須条件、dump 系との非互換、stage timing の条件とエラー。
- `engine/src/program/generate.cpp:24296-24314` — token ごとの直接実行と graph replay 経路の分岐。
- `engine/src/core/session.cpp:801-842` — `session_token` が層を順番に `block_layer` へ渡す実装、失敗時と任意の層ごと同期。
- `engine/sycl/src/program/generate.cpp:1969,5957-6000,13504-13518` と `engine/sycl/src/core/session.cpp:1148-1188` — SYCL parser、同じ制約と直接実行分岐、層の反復実装。
- 索引 `docs/cli/README.md:1036-1043,1142` — tool ID、root scope、および対象 option の掲載。索引は動作の根拠ではなく、文書配置の確認にのみ使用。

調査対象は上記 commit の checkout に限る。`--serve` の要求処理全体に対する効果、ならびに実機での backend 別挙動は実行せず確認していない。
