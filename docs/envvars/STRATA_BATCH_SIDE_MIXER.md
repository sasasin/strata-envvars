# `STRATA_BATCH_SIDE_MIXER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

batch window の中で、別変数 `STRATA_SIDE_MIXER` が有効にしている mixer 処理を CUDA graph の side stream に分岐させる許可スイッチです。未設定時は batch window の mixer 処理を通常の stream 上で行います。値を有効にしても `STRATA_SIDE_MIXER` の mode が 1 未満なら分岐しません。mode 1 では GDN gates と QSA indexer・scores・top-k を `side_` に、mode 2 では加えて GDN gate projection と QSA query chain を `side2_` に分けます。処理順序と並列スケジュールを変えますが、実装コメントは各処理を同じ計算の stream 違いとして説明しています（`engine/src/core/verify.cpp:1503-1515, 2077-2082`）。

この分岐は `Verifier::capture_batch` が batch window の graph を初めて記録するときに使われます。通常の単独 window では本変数の値にかかわらず batch 用の分岐条件は偽です（`engine/src/core/verify.cpp:4677-4699`）。

## 値と判定

共通の `env_on` helper は `std::getenv` の戻り値について、未設定でなく、かつ先頭 byte が NUL と `'0'` のどちらでもないことだけを判定します。文字列全体の parse、数値・真偽語の検証、大文字小文字変換、空白除去はありません（`engine/src/core/verify.cpp:336-339`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| すべての build | 無効 | `1`、`true`、`false`、`on`、` 0`（先頭 byte が `'0'` 以外） | 空文字、`0`、`0anything`（先頭 byte が `'0'`） |

したがって `false` も先頭が `'0'` ではないため有効です。`0anything` は後続文字を見ず無効です。負数・不正な数値・任意の文字列も、その先頭 byte が `'0'` 以外なら有効です。判定に数値境界はありません。batch 用関数の静的ローカル値として初回評価時に保存され、以後プロセス内で環境を変更しても再評価されません（`engine/src/core/verify.cpp:372`）。

## 有効になる条件

- batch window の graph capture が必要です。`capture_batch` が `batch_rec_` を立てて `record_window` を記録する経路でのみ本スイッチが条件に入ります（`engine/src/core/verify.cpp:4677-4690, 1506`）。
- `STRATA_SIDE_MIXER` の解決 mode が 1 以上である必要があります。明示値は `atoi` で整数化した後 0〜2 に clamp されるため、`1` は mode 1、`2` 以上は mode 2、`0`・負数・整数に変換できない文字列・空文字は mode 0 です。未設定時は CUDA device の属性を初回に調べ、compute capability 12.0 の既定を使い、それ以外は mode 0 です（コメント上、`STRATA_SM120_PERF=0` は 12.0 の既定を無効にします）。mode 0 なら `sidem` と `side_proj` は false で、batch 用スイッチが有効でも分岐しません（`engine/src/core/verify.cpp:272-292, 1503-1507, 1514-1515`）。
- `STRATA_USE_HIP` または `STRATA_GPU_METAL` build では `g_side_mixer()` が 0 を返すため、本変数だけでは分岐しません。CUDA 側では `STRATA_SIDE_MIXER` の値または CUDA device の既定 mode が使われます（`engine/src/core/verify.cpp:278-292`）。そのため `docs/SETTINGS.md:38` の NVIDIA and AMD という分類のうち、HIP/AMD は実装上この mixer 分岐の有効条件を満たしません。
- mode 1 は `side_` 分岐、mode 2 は `side_` と `side2_` の両方を有効にします。mode 1 で mode 2 専用の投影・query chain 分岐は追加されません（`engine/src/core/verify.cpp:1507, 1515, 1897-1920, 2318-2335`）。

## 実行時の詳細

`batch_side_mixer_on()` の関数内 `static const bool` が、batch window の `record_window` で初めて呼ばれた時点の環境値を一度読み取ります。未設定・空文字なら false です。graph capture は `exec_bm_` に該当 graph が既にあれば再記録を省くため、その graph の再利用時にも設定を読み直しません（`engine/src/core/verify.cpp:372, 1506, 4677-4689`）。

本変数は mixer の mode や計算内容を選びません。batch window では `batch_side` が true のときに限って `side_mixer` を許し、QSA indexer 側の処理を `side_` に記録します。`STRATA_SIDE_MIXER=2` 相当の mode なら、GDN projection と QSA query chain も `side2_` に記録します。無効時はこれらの処理を `cs` 上で順に記録します。コメント上、`STRATA_DF_BRANCH` は side mixer が有効なとき無効で、batch window でも適用されません（`engine/src/core/verify.cpp:1514-1515, 1548-1552, 2077-2082, 2318-2336`）。

この変数を直接上書きする CLI 引数や別設定の優先順位は、対象ソース内にありません。別変数 `STRATA_SIDE_MIXER` は mixer mode を決める独立した入力です。

## ログと測定値

対象変数の on/off を直接表示するログは見つかりません。dispatch の詳細出力では、別変数や GPU 既定値から決まった `side_mixer` mode と `side_proj` の値が `win pdl=... side_mixer=... side_proj=...` として記録されます。これは本変数自体の値を表示するものではありません（`engine/src/core/verify.cpp:1546-1548`）。

分岐の作成・同期に失敗すると `verify: the mixer branch's stream / events could not be created`、`verify: the mixer branch could not fork`、または該当 branch の `could not join` エラーを返します。batch graph の capture / instantiate / upload 側にも `verify: begin batch capture failed`、`verify: end batch capture: ...`、`verify: batch instantiate: ...` などの失敗経路があります（`engine/src/core/verify.cpp:1404-1412, 1508-1512, 1897-1920, 2318-2335, 4677-4702`）。

`docs/DETAILS.md` には `STRATA_SIDE_MIXER` の個別測定説明がありますが、この batch 用スイッチを有効にした測定値は確認できません（`docs/DETAILS.md:1266-1277`）。

## 根拠

- `engine/src/core/verify.cpp:336-339` — env helper の判定方法。
- `engine/src/core/verify.cpp:370-372` — 対象変数の説明と初回読み取りの cache。
- `engine/src/core/verify.cpp:272-292` — `STRATA_SIDE_MIXER` の値・backend 別既定。
- `engine/src/core/verify.cpp:1404-1412, 1503-1515` — stream 作成と batch window での適用条件。
- `engine/src/core/verify.cpp:1897-1975, 2077-2082, 2318-2336, 2411-2425, 2470-2558` — GDN / QSA の branch と join。
- `engine/src/core/verify.cpp:4677-4702, 5311` — batch graph capture の呼び出し・cache・失敗処理。
- `engine/src/core/verify.hpp:690-696` — mixer 用 side stream と event。
- `docs/SETTINGS.md:38`, `docs/DETAILS.md:1266-1277` — 対象名の設定一覧と関連 mixer の説明（実挙動の根拠はソース）。
