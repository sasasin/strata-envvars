# `STRATA_SPEC_CHECK_IDS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

## 役割

`strata-inkling` の `--spec-check` が生成した plain 実行と speculative drafter 実行それぞれの token ID 列を、標準出力へ追加表示する診断用スイッチです。値は token 生成、比較結果、終了コードを変更せず、ID 列の表示だけを切り替えます。実装は `cmd_spec_check` 内です（`engine/src/inkling2/ink_main.cpp:599-610, 632-658, 672-752`）。

この読み取りは `ink_main.cpp` にある `strata-inkling` の経路に属します。同ファイルは CMake の `strata-inkling` ターゲットに含まれます（`engine/src/inkling2/CMakeLists.txt:176-180`）。同じ環境変数名を読む別の Strata 所有箇所は見つかりませんでした。Metal と SYCL には別の main 実装がありますが、この変数名を読む箇所は確認できません（`engine/src/inkling2/metal/ink_metal_main.cpp:420-460`、`engine/src/inkling2/sycl/ink_sy_main.cpp:104-125`）。

## 値と判定

`cmd_spec_check` の最後の比較・結果表示の後で `std::getenv` を呼び、値が存在し、かつ先頭文字が ASCII `1` の場合だけ ID を表示します。文字列全体の比較や数値変換はしません（`engine/src/inkling2/ink_main.cpp:735-751`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `--spec-check` が実行され ID 出力位置まで到達 | 表示しない | `1`、`10`、`1anything`（先頭が `1`） | 空文字、`0`、`true`、`01`、` 1`（先頭が `1` ではない） |

大文字小文字、空白除去、文字列全体の妥当性検査はありません。未設定と空文字はいずれも表示しません。`getenv` の結果は関数内 static に保存されず、チェック処理がこの位置へ到達したときに一度読みます（`engine/src/inkling2/ink_main.cpp:745`）。

## 有効になる条件

- `strata-inkling` で `--spec-check N` を指定し、`N` の `std::atoi` 結果が正である必要があります。`--spec-check` 自体はこの環境変数では有効になりません（`engine/src/inkling2/ink_main.cpp:842, 966-968, 1062-1069`）。
- `--spec-check` の実行には `--prompt-ids` のリストまたは `@file` が必要です。指定がないか ID リストを解析できない場合は `--spec-check needs --prompt-ids ...` を stderr に出して終了コード 2 となり、ID 表示位置には到達しません（`engine/src/inkling2/ink_main.cpp:957-963, 1062-1069`）。
- モデルを開き、backend 初期化・slot 確保・plain と speculative の生成が成功して、表示箇所まで処理が進む必要があります。これらの途中で失敗すると関数は先に戻り、ID は出ません（`engine/src/inkling2/ink_main.cpp:603-611, 623-628, 647-654, 686-687, 706-707, 726-727`）。
- CPU/GPU の選択や build 時に組み込まれた backend は、この値判定を変えません。`make_default_backend` は force-CPU 指定時に CPU を返し、それ以外は build macro に応じた CUDA / EP CUDA / HIP / Metal / SYCL backend を選び、該当しなければ CPU を返します（`engine/src/inkling2/ink_backend.h:198-215`）。ただし、別実装の Metal/SYCL main でこの変数が有効になるとは確認できません。
- `STRATA_SPEC_CHECK_QUICK=1` は比較処理の後で verify-window 比較を省略しますが、ID 表示分岐より後に評価されるため、`STRATA_SPEC_CHECK_IDS` の表示を抑止しません（`engine/src/inkling2/ink_main.cpp:745-755`）。

## 実行時の詳細

CLI の `--spec-check` の引数は `std::atoi` で読み、正数のときに prompt ID を解析して `cmd_spec_check` を呼びます。関数では同じ prompt から plain B=1 実行を2回行い、その後 speculative 実行を行います。`STRATA_SPEC_CHECK_IDS` はその生成と「speculative vs plain」の比較表示が終わった後に判定されます（`engine/src/inkling2/ink_main.cpp:966-968, 1062-1069, 632-658, 672-752`）。

有効時は `[spec-check] IDS plain:` に plain 実行の `a1`、`[spec-check] IDS drafter:` に speculative 実行の `b` を出力します。各列は整数 ID をカンマ区切りで並べます。環境変数は比較用ベクトルや `rc` を変更せず、ID 出力後の既存処理が差異を検出した場合は引き続き `rc = 1` になります（`engine/src/inkling2/ink_main.cpp:735-752`）。unset または無効値の場合はこの2行を出力しません。

## 根拠

- `engine/src/inkling2/ink_main.cpp:599-610` — `cmd_spec_check` のモデル・backend 初期化。
- `engine/src/inkling2/ink_main.cpp:632-658, 672-752` — plain / speculative の生成、ID 表示、差異による終了値。
- `engine/src/inkling2/ink_main.cpp:842, 957-968, 1062-1069` — CLI 引数と実行条件。
- `engine/src/inkling2/ink_backend.h:198-215` — build macro と force-CPU による backend 選択。
- `engine/src/inkling2/CMakeLists.txt:176-180` — `ink_main.cpp` を含む `strata-inkling` ターゲット。
