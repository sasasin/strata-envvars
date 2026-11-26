# `strata --host-core`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID / scope | `strata-engine` / `root/`（エンジン引数） |
| 値 | `first`、`last`、`sibling` |
| 既定値 | `first`（従来の配置） |
| 関連環境変数 | `STRATA_HOST_CORE`（CLI 値が空のときに参照） |

## 値と既定値

`--host-core` は値を 1 個取り、`first`、`last`、`sibling` のいずれかだけを受理します。省略時は `first` です。`first` は既定の host core（検出された最初の物理 core）を使います。空文字やそれ以外の値は無効です。オプションを値なしで末尾に置くと `--host-core needs a value` を stderr に出して終了コード 2、未知の値なら `strata generate: unknown --host-core value '…' (expected first, last or sibling)` を stderr に出して終了コード 2 で戻ります（`engine/src/program/generate.cpp:3844-3846,3947-3953`）。

## 実行時の動作

値は CPU pool と session の thread affinity を設定する前に適用されます。`--host-core` に値が指定されていれば `STRATA_HOST_CORE` より優先されます。CLI 値を省略した場合に限り環境変数を読み、`last` または `sibling` なら pool の設定を変更します。環境変数の値はこの箇所では検証されず、`first` や未知の値は設定変更を起こさず既定の `first` のままです（`engine/src/program/generate.cpp:4696-4702`）。同じオプションを複数回指定した場合は parser が `o.host_core` を都度代入するため、最後の指定値が残ります（`engine/src/program/generate.cpp:3842-3847,3947-3953`）。

- `first`: host thread は従来どおり最初の予約 core を使い、worker は残りの core を使います。
- `last`: hybrid CPU では適用されません。非 hybrid で host 用 core と worker core が検出されている場合、最後の worker core を host 用へ移し、元の host core を worker 側の先頭へ移します。したがって配置を変えるだけで、計算結果は変えないと help に記載されています（`engine/src/kernels/cpu/pool.cpp:249-258`; `engine/src/program/generate.cpp:1449-1455`）。
- `sibling`: host core の SMT sibling が検出された場合、host をその sibling に移し、worker 配置からその論理 processor を除きます。最初の論理 processor は worker に割り当てません。sibling がない場合は切替条件が成立しないため、`first` 相当の配置のままです（`engine/src/kernels/cpu/pool.cpp:259-265`）。

この選択を使った topology は CPU pool の worker 配置計画に反映されます。session 初期化では `planned_host_core()` の結果に host thread を pin し、正常終了時の後始末で元の affinity を復元します（`engine/src/kernels/cpu/pool.cpp:249-268`; `engine/src/core/session.cpp:550-580`）。

## 適用条件と副作用

このオプションは host thread と CPU pool worker の CPU affinity 配置を変えます。`last` の変更は非 hybrid CPU に限られ、`sibling` は SMT sibling が検出された場合に限られます。`first` は従来の配置を保ちます。起動時に pool/session が使う topology を変える設定であり、実行中に動的変更する処理は確認できません。

host affinity の設定に失敗すると `strata cpu pool: host affinity for CPU … failed: …; previous affinity kept`（Windows では `host CPU Set selection … failed`）を stderr に出し、pin 処理は無効な保存状態を返します。session 初期化は処理を続け、失敗時に元の配置が保たれる実装です（`engine/src/kernels/cpu/pool.cpp:699-722`; `engine/src/core/session.cpp:558-571`）。pool/thread の配置は起動時に `strata generate: … pool workers … the host thread on … (--host-core …)` と stderr に表示されます（`engine/src/program/generate.cpp:9022-9036`）。

## 根拠

- `engine/src/program/generate.cpp:863-864` — option の設定フィールド。
- `engine/src/program/generate.cpp:1449-1455` — help にある値の説明、既定配置、hybrid/SMT 条件。
- `engine/src/program/generate.cpp:3842-3847,3947-3953` — 値の取得、parser validation、エラー経路。
- `engine/src/program/generate.cpp:4696-4702` — CLI と `STRATA_HOST_CORE` の優先関係、pool 設定への反映。
- `engine/src/kernels/cpu/pool.cpp:81-85,249-268` — 初期値と topology に対する `last` / `sibling` の変換。
- `engine/src/kernels/cpu/pool.cpp:699-722` — host affinity の適用失敗時の診断と既存配置の維持。
- `engine/src/core/session.cpp:550-580` — session 初期化時の host pin と終了時の復元。
- `engine/src/program/generate.cpp:9022-9036` — pool と host thread の配置診断出力。

調査範囲は上記 revision の Strata ソースです。環境変数自体の独立した文書仕様や、各 OS の affinity API の外部仕様は対象にしていません。
