# `STRATA_TEST_CONC_ON_HOST_CPU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows の piped concurrent prompt-read 経路で、読み取り thread と doorbell thread を一度ホスト thread の CPU set に置いてから、通常の affinity 切り替えを行うテスト用スイッチです。環境変数の値は解釈せず、設定されているかだけを見ます。通常の並行読み取り自体を有効化する変数ではありません（`engine/src/program/generate.cpp:21024-21054,21074-21111`）。

`STRATA_PIPED_CONCURRENT` によって並行読み取りが有効で、他の無効化条件に当たらず、画像なしの piped prompt read が始まる場合に限り関係します。`piped` は `--batch > 0`、`--batch-groups > 1`、layer-split pipeline の stage 数 `n_pipe > 1` で成立します（`engine/src/program/generate.cpp:17529-17533,21024-21054`）。ソースの `#if defined(_WIN32)` 内だけで宣言・参照されるため、Windows 以外ではこの名前を読みません（同 `21074-21111`）。

## 値と判定

Windows で上記の並行読み取り経路に初めて入ったとき、`std::getenv(...) != nullptr` の結果を関数内 `static const bool` に保存します。文字列変換・数値判定・trim はありません（`engine/src/program/generate.cpp:21054,21074-21077`）。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| Windows build、並行読み取り経路に到達 | `false` | 環境変数が存在する任意の値。`1`、`0`、`true`、`false`、空文字、`0anything` はすべて `true` | なし（未設定だけ `false`） |
| Windows 以外 | 読み取りなし | 該当なし | 該当なし |

経路に到達しない場合は static 初期化も行われません。到達後はプロセス内で値が cache されるため、実行中に環境を変更しても反映されません（同 `21054-21077`）。

## 有効になる条件

- Windows build であること。非 Windows の実装はこの変数を参照せず、別の affinity 処理になります（`engine/src/program/generate.cpp:21074-21111`）。
- `--batch > 0`、解決済み `--batch-groups > 1`、`n_pipe > 1` の layer-split piped 経路であること（同 `17529-17533`）。
- `STRATA_PIPED_CONCURRENT` が設定され、`atoi` の結果が 0 以外であること。未設定、空文字、`0`、`false`、`0anything` はこの機能を有効にしません（同 `21024-21029`）。
- `STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS` がそれぞれ `atoi != 0` でないこと、`--pcie-mode dma` でないこと、helper cache を使わないこと、blob を stage する expert source でないこと、GGUF source と arena source 以外の expert source でないこと。最初に該当した理由を `strata batch: STRATA_PIPED_CONCURRENT is off beside <理由>` と stderr に出して並行読み取りを無効化します（同 `21027-21045`; `engine/include/strata/program/batch_read.hpp:30-53`）。
- prompt に画像がないこと（`req_imgs.empty()`）。さらに prompt token 数 `b0-a0` が `STRATA_PIPED_CONCURRENT_MIN` の値以上であること。後者は未設定時 0、設定時 `atoll` 後に 0 未満を 0 に clamp します（`engine/src/program/generate.cpp:21047-21054`）。

これらの条件を満たさない場合、この変数は CPU affinity に影響しません。上記の条件を満たしても、ホストの CPU set 取得に失敗または空集合となった場合は、その集合を新 thread に設定しません（同 `21077-21085,21102-21111`）。

## 実行時の詳細

並行読み取り経路では、Windows 上でこの変数が設定されていると、現在の thread の選択 CPU set を `GetThreadSelectedCpuSets` で取得し、読み取り thread と doorbell thread の affinity 初期化時にその set を `SetThreadSelectedCpuSets` で適用します。取得が失敗した場合は保存先を空にし、適用を飛ばします。API の戻り値や失敗理由を別途検査・記録する処理はありません（`engine/src/program/generate.cpp:21074-21111`）。

その後の affinity は `STRATA_PIPED_CONCURRENT_UNPIN` に従います。未設定または `atoi != 0`（既定）なら、ホスト set を一時設定した後 `SetThreadSelectedCpuSets(..., nullptr, 0)` で解除します。`STRATA_PIPED_CONCURRENT_UNPIN=0` など `atoi` が 0 になる値では解除せず、ホスト thread の set に留めます。この変数はその test A/B の初期配置を可能にし、解除するかどうかは別変数が決めます（同 `21068-21111`）。Windows 以外では `conc_on_host` 自体がなく、`conc_unpin` が有効かつ `--aux-cpus` が有効でない場合に `place_off_host()` を試みます（同 `21102-21111`; `engine/include/strata/platform/aux_cpus.hpp:315-323`）。

並行 read の入口自体は `--batch-groups` の piped 経路と環境変数で決まり、通常の CLI/server モード別条件はこの箇所にはありません。prompt の画像有無は条件に含まれます（`engine/src/program/generate.cpp:17529-17533,21024-21054`）。

## ログと測定値

この変数が設定され、並行読み取り経路に入ると、CPU set 取得の結果（件数）と解除方針を stderr に出します。

```text
strata batch: test: the read's and the doorbell threads start on the host thread's N CPU set(s), then leave them (the fix)
```

`STRATA_PIPED_CONCURRENT_UNPIN` が `atoi == 0` の場合、末尾は `and stay there (as on Linux)` です。変数が未設定ならこの test ログは出ません。並行読み取りが有効な read では別途、読み取り token 数・時間・同時 decode 行数などの `strata batch: read ... (concurrent, ...)` 行が stderr に出ます。CPU set API の失敗を示す専用ログはありません（`engine/src/program/generate.cpp:21086-21093,21263-21269`）。

`docs/BATCHING.md:253-281` は `STRATA_PIPED_CONCURRENT` による並行 prompt read と無効化条件を説明していますが、この Windows 専用テスト変数の記載はありません。ここではソースで確認できる affinity 制御だけを記述し、資料中の測定値をこの変数の効果として扱っていません。

## 根拠

- `engine/src/program/generate.cpp:17529-17533` — piped batch/groups/layer-split 条件。
- `engine/src/program/generate.cpp:21024-21054` — concurrent read の設定判定、他設定による無効化、画像と prompt 長の条件。
- `engine/src/program/generate.cpp:21068-21111` — Windows 専用の対象変数読み取り、CPU set の取得・thread への設定・解除、および非 Windows 分岐。
- `engine/src/program/generate.cpp:21086-21093,21263-21269` — stderr のログ。
- `engine/include/strata/program/batch_read.hpp:30-53` — concurrent read の無効化理由。
- `engine/include/strata/platform/aux_cpus.hpp:315-323` — 非 Windows 経路で呼ばれる `place_off_host()`。
- `docs/BATCHING.md:253-281` — 並行 prompt read の説明との照合。
