# `STRATA_SLOT_COPY_BATCHSYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

バッチ slot のセッション状態と QSA K/V を GPU 間で直接コピーする経路において、各コピーの完了を個別に待たず、コピーを各 device の private copy stream に積んでから device ごとにまとめて同期するかを制御する。既定の未設定値ではこのまとめ待ちは無効で、コピー関数は通常どおり完了を待つ。変数が有効でも `STRATA_SLOT_COPY_DIRECT` が有効でなければこの分岐に到達しない。slot が持つ状態の内容やコピー方向を選ぶ設定ではない（`engine/src/program/generate.cpp:573-582,16864-16902`）。

## 値と判定

`slot_copy_batchsync_env()` は `std::getenv` の結果を関数内 `static const bool` に保存し、値が存在し、かつ先頭文字が `'0'` でなければ有効とする。文字列全体や数値としての妥当性は検査しない。したがって空文字、`1`、`true`、`false`、先頭が空白の値、`0anything` 以外の文字列は有効、`0` や `0anything` は無効。大文字小文字の変換はないが、文字列比較も行わない（`engine/src/program/generate.cpp:577-582`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の読み取り | 無効 | 空文字、`1`、`true`、`false`、` 0` | `0`、`0anything` |
| parallel stack の自動既定値が適用される場合 | 環境に未設定なら `1` を設定 | 上記と同じ | 明示した `0` などは上書きされず無効のまま |

自動既定値を設定する処理は `getenv(name) != nullptr` を確認するため、空文字や `0` も「ユーザーが設定済み」として保持される（`engine/src/core/arch_defaults.cpp:253-260,302-310,346-356,433-441`）。ただしこの変数自身の読み取り規則では空文字は有効である。

別経路として、Terminal の opt-in replica profile は条件を満たすと `cfg["env"]` にこの変数を `1` として追加する。親プロセス環境に同名キーがあれば追加せず、既存の `cfg["env"]` 値も `setdefault` で保つ。server の `child_env()` は `cfg["env"]` を継承環境へ後から適用するため、既存 config 値があれば親プロセス環境値より優先し、なければ親環境値が子 engine に渡る（`terminal/strata_control/replica_profile.py:102-122`; `terminal/strata_control/setup_config.py:487-500`; `terminal/serve/server.py:4007-4028`）。replica profile が追加した値も engine 側では通常の環境値として扱われる。

## 有効になる条件

- エンジンのバッチ slot admission / restore が direct slot copy を使うこと。`STRATA_SLOT_COPY_DIRECT` は別途読み取られ、未設定・空文字・先頭が `0` の値では direct 経路を使わない（`engine/src/program/generate.cpp:16868-16873,16904-16916,16955-16979`）。この変数単独では host image を介する既定コピー経路を変更しない。
- Metal build は `copy_to_slot` / `copy_from_slot` で Metal の slot-copy 関数に分岐して戻るため、この CUDA/HIP 用 direct-copy 分岐と本変数の判定を通らない（`engine/src/program/generate.cpp:16904-16912,16958-16965`）。
- CUDA/HIP 系で直接設定すれば、direct slot copy が呼ばれるときに利用される。自動で `1` を設定するのは限定条件下のみ: Linux CUDA は `o.batch >= 2`（`apply_parallel_defaults_cuda` が Linux CUDA 専用ビルド条件内で呼ばれる、`engine/src/core/arch_defaults.cpp:248-260`、`engine/src/program/generate.cpp:4410-4414`）。HIP の arch defaults では discrete RDNA3 は `batch_slots >= 2` かつ `STRATA_GFX11_DEFAULTS=0` による無効化がなく、`qwen_defaults_026()` が false のときに parallel stack に含まれる（`engine/include/strata/core/gfx11_extra.hpp:27-31,116-133`）。gfx1151 の Windows 既定値は Windows・gfx1151・2 slot 以上で、`STRATA_GFX1151_DEFAULTS=0` で無効化される（`engine/src/core/arch_defaults.cpp:240-245`）。
- 自動既定値の処理は設定済みの値を優先するため、`STRATA_SLOT_COPY_BATCHSYNC=0` は自動的な有効化を拒む（前掲 `arch_defaults.cpp` の行）。既定値テーブルに同居する `STRATA_SLOT_COPY_DIRECT=1` も設定されるが、個別に明示した値はそれぞれ保持される（`engine/src/core/arch_defaults.cpp:226-237`）。
- Terminal replica profile の自動設定は、profile が opt-in され、複数 GPU・対応モデル・VRAM / RAM 条件などを満たして profile が適用される場合に限る（`terminal/strata_control/replica_profile.py:77-99,102-122`）。これは engine 自身の arch defaults とは別の server config 経由の設定である。

## 実行時の詳細

判定値は `slot_copy_batchsync_env()` が初めて呼ばれた時点で一度だけ読み込まれ、関数内 static に保持される。以後のプロセス環境変更は反映されない。関数は direct slot copy 内から呼ばれ、copy 開始前に各 device を同期し、`queued` を全 stage の checkpoint copy と QSA K/V copy に渡す。queued が true の場合、状態コピーを private copy stream に積み、streamed K/V の residency refresh を event でコピー後に順序付け、そのあと全 device を同期してから処理を続ける。false の場合はコピーごとの待機を使う（`engine/src/program/generate.cpp:16873-16902`; `engine/src/core/conversation_state.cpp:467-495`; `engine/src/core/conversation_snapshot.cpp:625-662`; `engine/include/strata/core/conversation_snapshot.hpp:28-33,113-117`）。

この copy は slot への admission と、slot から main session へ戻す通常 resume（checkpoint 指定なし）の双方で共有される。slot admission は `--batch` の継続要求で、restore は slot を再利用する要求で呼ばれる（`engine/src/program/generate.cpp:16904-16916,16955-16979,19863-19884,23585-23595`）。同じ source state から同じ宛先へ同じ byte 列をコピーし、生成や選択の計算を変更する分岐ではない。ソースコメントは各 device の約116コピーを一度ずつ同期する設計を示すが、測定値としての速度向上はここからは断定できない（`engine/src/program/generate.cpp:573-576,16864-16888`）。

## ログと測定値

変数の値を直接報告するログはない。CUDA/HIP の arch defaults がこの変数を自動設定したときは、環境に未設定だった他の parallel switches とまとめて stderr に `strata: gfx11 (RDNA3): exact parallel-request switches on for ...` または `strata: gfx1151 (Strix Halo): the exact parallel-request switches are on for ...` を出し、その一覧に `SLOT_COPY_BATCHSYNC` が含まれる（`engine/src/core/arch_defaults.cpp:346-356,433-441`）。Linux CUDA の `apply_parallel_defaults_cuda` は既定値を設定するが、この処理自体はログを出さない（`engine/src/core/arch_defaults.cpp:253-260`）。

direct slot copy の前後の device 同期失敗は `batch slot copy: device sync failed` として返り、admission 側では `strata serve: batch admission failed: ...` を stderr に出してその slot の継続を止める。途中の copy 失敗でも同期を試みてから失敗を返す。resume 側は `strata batch: restoring slot %d failed (%s); reading the prompt` を stderr に出し、prompt を最初から読む経路へ戻る（`engine/src/program/generate.cpp:16875-16902,19863-19875,23590-23595`）。比較性能の実測値はこの変数について記載しない。

## 根拠

- `engine/src/program/generate.cpp:573-582` — 値の読み取り・変換・static cache。
- `engine/src/program/generate.cpp:16864-16916,16955-16979` — direct slot copy と batchsync の適用箇所。
- `engine/src/core/arch_defaults.cpp:226-260,302-357,423-441`、`engine/include/strata/core/gfx11_extra.hpp:27-31,116-137` — parallel stack の既定値、適用条件、明示値の優先。
- `terminal/strata_control/replica_profile.py:102-122`、`terminal/strata_control/setup_config.py:487-500`、`terminal/serve/server.py:4007-4028` — opt-in replica profile と子 engine 環境への引き渡し。
- `engine/src/core/conversation_state.cpp:467-495`、`engine/src/core/conversation_snapshot.cpp:625-662`、`engine/include/strata/core/conversation_snapshot.hpp:28-33,113-117` — queued copy と residency refresh の同期順序。
- `engine/src/program/generate.cpp:19863-19875,23585-23595` — restore / admission の観測可能な失敗経路。
