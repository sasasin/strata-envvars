# `STRATA_ADAPT_ASYNC_WAIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

expert arena を使う非同期適応層（`--adapt-async 1`）で、GPU cache への expert copy-in が完了するまで適応層の tick を待つか決めます。既定では待ちます。待機を無効にすると、その tick では完了をポーリングし、未完了なら呼び出し元へ戻って後続の tick で再確認します。

この変数はコピーの実行そのものや適応層を有効化する設定ではありません。arena 以外のソースでは `a_wait` が常に false となり、この変数は待機動作に影響しません。読み取り箇所は `src/program/generate.cpp` の `a_env("STRATA_ADAPT_ASYNC_WAIT", 1)` だけです（同ファイル 9062-9070 行）。

## 値と判定

値は `a_env` helper が `std::getenv()` で読み、未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で整数に変換します。変換後が 0 なら待機しません。0 以外（負数を含む）なら待機します。

| 環境値 | `a_env` の結果 | arena モードでの動作 |
|---|---:|---|
| unset | 既定値 `1` | 待つ |
| 空文字 | 既定値 `1` | 待つ |
| `0`、`00`、`0abc` | `0` | 待たずにポーリング |
| `1`、`1abc`、`-1` | 0 以外 | 待つ |
| 数字として解釈できない文字列（例: `true`） | `0` | 待たずにポーリング |

`atoi` は文字列全体の厳密な検証をしません。先頭の空白や符号の後にある数値部分を変換し、数値の後ろの文字は判定しません。先頭から整数を読み取れない文字列は 0 として扱われます。大文字小文字の比較はありません。

## 有効になる条件

`a_wait` は `a_arena && ...` として設定されるため、expert arena（`srcp == &arena_src`）以外では常に false です。設定が実際の適応に使われるには、`--adapt-async 1` で非同期適応層が開始され、usage table が空でない必要があります。非同期経路は `--serve` と有効な適応設定（`--adapt-every`、`--adapt-swaps`）を必要とし、arena では layer split および `--pipeline-windows 2` と併用できません。条件を満たさない場合、コードは理由を stderr に出して blocking adaptive tier に切り替えます（`src/program/generate.cpp:6967-6993,9071-9079`）。

通常の resident RAM モードの非同期適応層では、copy-in の完了確認に `drain` の値を使い、この変数は参照されません。arena ではコピー元がすでに arena 内にあり、round は copy-in のみです（`src/program/generate.cpp:9028-9036,9057-9070`）。

## 実行時の詳細

変数は適応層の初期化時に通常の環境変数として読み、`a_wait` に保存されます。static cache ではありませんが、以後の tick ごとには読み直しません。したがって、その適応層が動作中にプロセス環境を変更しても、この実行中の値には反映されません（`src/program/generate.cpp:9062-9070`）。

copy-in の状態（`AState::SwapIn`）で、コードは `a_ready(drain || a_wait)` を呼びます。待つ場合、helper thread を join し、使用した CUDA event を `cudaEventSynchronize()` で待ちます。待たない場合は helper thread の idle 状態と `cudaEventQuery()` を調べ、どちらかが未完了なら false を返します。その tick はそこで戻り、後続の tick で再確認します（`src/program/generate.cpp:9218-9229,9333-9344`）。drain 時は環境値にかかわらず待機します。

新しい expert の residency table 更新と旧 expert の release は `a_ready()` が成功した後に行われます。つまり待機を無効にしても、コピー未完了の expert をコピー完了済みとして扱う分岐にはなりません。arena の status 行には `wait 0` または `wait 1` が出ます（`src/program/generate.cpp:9333-9344,13025-13034`）。

`STRATA_ADAPT_ASYNC_BATCH` が正で copy-in を複数 batch に分ける場合、待機ありでも通常 tick は着地した batch を反映して次の batch を投入した後に戻ります。round drain 時は `drain` が true のため、残りの batch も順に待って完了させます（`src/program/generate.cpp:9200-9205,9333-9349`）。

`docs/DETAILS.md` は既定値 1 が次の tick でコピーを待ち、expert が GPU resident になる window をタイミング依存にしないと説明しています（182-184 行）。ソースも待機時に copy-in の event を同期し、その後に residency を更新する順序になっています。資料に記載された性能値は arena の非同期適応層全体の測定であり、この変数単体の性能効果を示すものではありません。

## 根拠

- `src/program/generate.cpp:9062-9070` — `a_env` の既定値・`atoi` 変換、arena 条件付きの `a_wait` 設定。
- `src/program/generate.cpp:6967-6993` — 非同期適応層の有効条件と blocking tier への切り替え。
- `src/program/generate.cpp:9028-9036,9057-9079` — arena の copy-in-only 経路と非同期 tier の開始条件。
- `src/program/generate.cpp:9218-9229,9333-9344` — wait と poll の差、event 完了後の residency 更新。
- `src/program/generate.cpp:13025-13034` — 非同期適応層の統計出力と arena の `wait` 表示。
- `docs/DETAILS.md:180-187` — arena での既定待機動作と関連資料。
