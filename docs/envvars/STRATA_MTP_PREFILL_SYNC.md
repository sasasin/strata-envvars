# `STRATA_MTP_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

MTP drafter がプロンプト中の K/V を自身の `MtpDrafter::prefill` で計算するとき、入力をグループ単位で逐次処理する旧方式を選ぶか、入力レコードをまとめて転送してグループを連続投入する E-4 方式を選ぶかを制御します。MTP が無効な実行や、メイン prefill が draft K/V を batched 経路で作れた場合には、この設定による分岐を通りません（`src/program/generate.cpp:11006-11027`, `src/prefill/prefill.cpp:1916-1937`）。

## 値と判定

`std::getenv` で取得し、設定されていれば `std::atoi(value) != 0` で判定します。文字列全体の検証や範囲制限はありません。

| 値 | 判定 |
| --- | --- |
| 未設定 | `STRATA_USE_HIP` が定義されたビルドでは旧方式（true）。それ以外では E-4（false）。 |
| 空文字 | `atoi("")` は 0 となるため E-4。 |
| 数値の先頭部分が 0 | 旧方式を無効化。例: `0`, `0xyz`。 |
| 数値の先頭部分が非ゼロ | 旧方式を有効化。例: `1`, `-1`, `2`, `1xyz`。 |
| 数字で始まらない文字列 | `atoi` の結果が 0 となるため E-4。先頭空白と符号の後に数字があれば、その数値部分で判定。 |

したがって、`=0` は HIP の既定動作も E-4 に切り替え、`=1` は非 HIP の既定動作も旧方式に切り替えます。読み取り結果は関数内の `static` 変数に保存されるため、最初の評価後にプロセス環境を変更しても反映されません（`src/core/mtp.cpp:1425-1435`, `sycl/src/core/mtp.cpp:1380-1387`）。

## 有効になる条件

- MTP drafter が有効で、プロンプトの draft K/V を作る必要があること。
- `Prefill::draft_kv` がその入力を batched 経路で処理しないこと。たとえば `STRATA_MTP_BATCH=0`、drafter の K/V が通常の paged/ring でない、hybrid K/V、別 GPU、必要な tensor や scratch 条件の不足などで batched 経路は decline し、呼び出し元が `mtp.prefill(...)` に進みます。ring K/V は `STRATA_MTP_BATCH_RING` などの条件にも左右されます（CUDA: `src/prefill/prefill.cpp:1924-1959`; SYCL: `sycl/src/prefill/prefill.cpp:1592-1629`; 呼び出し: `src/program/generate.cpp:11006-11027`, `sycl/src/program/generate.cpp:8055-8063`）。
- Metal は `MtpDrafter::prefill` 冒頭で `metal_engine::mtp_prefill` に委譲して戻るため、この選択を評価しません（`src/core/mtp.cpp:1465-1470`）。
- 既定値の切り替えは `STRATA_USE_HIP` のビルド macro によります。実行時の OS 名や GPU 型を調べる分岐はありません（`src/core/mtp.cpp:1427-1434`, `sycl/src/core/mtp.cpp:1380-1387`）。

CLI 引数による直接の上書きは見つかりませんでした。E-9 の batched 経路側には別の `STRATA_MTP_BATCH` / `STRATA_MTP_BATCH_RING` 等の選択条件がありますが、そこで処理が完了すると本変数の判定には進みません。

## 実行時の詳細

E-4（判定 false）では、`n` 件分の token / step / position レコードをまとめて構成・転送し、`max_t_` 件以下のグループごとに device copy と graph を同じ stream に投入します。`sync=true` なら最後に stream を同期し、`sync=false` なら投入後に query して戻ります。旧方式（判定 true）では、`sync` 引数にかかわらず各グループの入力を host 側に用意して graph を実行し、グループごとに stream を同期してから次へ進みます（`src/core/mtp.cpp:1486-1567`; SYCL 実装は `sycl/src/core/mtp.cpp:1388-1538`）。いずれも `first_needed` より前で window が再利用しないセルは飛ばします。

prompt chunk callback は `use_mtp` が true で E-9 batched 経路が成功しなかった場合に `mtp.prefill` を呼び、失敗時は callback が false を返します（`src/program/generate.cpp:11006-11027`, `17773-17780`; SYCL: `sycl/src/program/generate.cpp:8055-8063`, `12390-12402`）。通常の prompt pass でも MTP 有効時に呼び出され、pipelined window では `sync=false` で呼ばれます（`src/program/generate.cpp:14871,14939`; SYCL: `sycl/src/program/generate.cpp:10532,10594`）。merged window の経路にも呼び出しがあります（`src/program/generate.cpp:17033-17036`）。この変数専用のログや警告はありません。allocation、upload、graph launch、同期が失敗すると `mtp prefill: ...` のエラー文字列を設定して false を返す経路があります（`src/core/mtp.cpp:1488-1495,1512-1514,1523-1540,1545-1563`; SYCL: `sycl/src/core/mtp.cpp:1389-1424,1429-1502`）。

コードコメントには、HIP の一部環境で E-4 が停止した観測と旧方式の比較が記されていますが、これはコメントに記録された条件での報告です。現行ソースから他の環境での性能や停止の有無は判断できません（`src/core/mtp.cpp:1480-1485`）。

## 根拠

- 直接の環境読み取りと既定値: `src/core/mtp.cpp:1425-1435`, `sycl/src/core/mtp.cpp:1380-1387`。
- 二方式の選択、E-4 のまとめ投入と末尾同期、旧方式のグループ同期: `src/core/mtp.cpp:1465-1567`, `sycl/src/core/mtp.cpp:1363-1538`。
- prompt prefill からの呼び出しと失敗伝播: `src/program/generate.cpp:11006-11027`, `sycl/src/program/generate.cpp:8055-8063`。
- E-9 batched 経路の decline 条件: `src/prefill/prefill.cpp:1916-1959`, `sycl/src/prefill/prefill.cpp:1592-1629`。
