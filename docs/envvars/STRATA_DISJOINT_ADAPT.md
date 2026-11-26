# `STRATA_DISJOINT_ADAPT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

主 GPU の adaptive expert cache が入れ替え候補を作るとき、helper GPU の cache が現在保持している `(layer, expert)` を候補から外す。これにより、適応によって helper と主 GPU の cache に同じ expert を載せる選択を避ける。helper cache の中身を変更したり、adaptive tier 自体を有効にしたりする設定ではない。環境変数を無効にした場合も、peer cache など別の既存候補除外規則はそのまま働く。CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` に同じ読み取りと helper 判定がある。`RemoteExperts::holds` はその時点で cache が該当 expert を保持するかを返す（`engine/include/strata/core/remote_experts.hpp:41-43`、SYCL 版 `engine/sycl/include/strata/core/remote_experts.hpp:37-39`）。

## 値と判定

両実装とも `std::getenv` の戻り値を `std::atoi` に渡し、未設定でなく、変換結果が 0 以外なら有効とする。文字列全体の妥当性検査や `1` との比較はない。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 系または SYCL 系の `generate` 実装 | 無効（`v == nullptr`） | `1`、`-1`、`2tail`、` 1`（`atoi` が 0 以外を返す場合） | 空文字、`0`、`0anything`、`true`、`false`、数字に変換できない文字列 |

したがって、空文字は「設定済み」でも無効。先頭の空白と符号は `atoi` の変換規則に従い、数字列の後ろは検査されない。数値に変換できない場合は 0 となる。範囲制限・clamp・別値への fallback はない。`int` の範囲を超える入力を安全に検査する処理もないため、その場合の変換結果はこのコードから規定できない。表の読み取り式は CUDA/HIP 系 `engine/src/program/generate.cpp:10232-10240` と SYCL 系 `engine/sycl/src/program/generate.cpp:5768-5777` にある。

## 有効になる条件

- `generate` が該当する CUDA/HIP 系または SYCL 系実装で動くこと。環境値の判定箇所自体に OS 固有の条件分岐はない（上記各ファイルの読み取り箇所）。
- 主 cache の adaptive tier が実際に候補を選ぶこと。通常のオプション既定値は `--adapt-every` が 4、`--adapt-swaps` が 96 で、CLI の `--adapt-every` と `--adapt-swaps` はそれぞれ独立に設定できる（`engine/src/program/generate.cpp:1045-1048,1084-1085,4058-4061,4202`、SYCL 系 `engine/sycl/src/program/generate.cpp:692-694,721,2052-2054,2166`）。`adapt_every` または `adapt_swaps` が 0 以下なら adaptive tier が動かない経路がある（例: CUDA/HIP 系 `engine/src/program/generate.cpp:15601-15603,24704-24705`、SYCL 系 `engine/sycl/src/program/generate.cpp:13800,13858`）。この環境変数はその条件を上書きしない。
- helper cache が設定・初期化され、少なくとも一つの helper が対象 expert を保持していること。候補判定は `drive.d.remote[]` の `remote_count` 件を調べる。helper cache は `--expert-cache-remote` に対応する値が正の場合に追加される（CUDA/HIP 系 `engine/src/program/generate.cpp:10235-10243`、SYCL 系 `engine/sycl/src/program/generate.cpp:5772-5780`）。helper がない、またはその expert を保持していない場合、この設定による候補除外は起きない。
- helper に保持されていても、主 cache にすでに載っている expert は元から「missing expert」の候補ではない。残る候補にも使用回数、peer/remote ownership、fetch 状態、入替利得など既存条件が適用される（CUDA/HIP 系 `engine/src/program/generate.cpp:15354-15375,24728-24745`、SYCL 系 `engine/sycl/src/program/generate.cpp:8854-8877,13874-13895`）。

## 実行時の詳細

各実装は `RemoteExpertOpt::init` の後に値を読み、ローカルの `const bool disjoint_adapt` に保存する。従って、同じ `generate` 実行内で後からプロセス環境が変わっても、この判定値は読み直されない。一方、helper の保持状態は `helper_holds` が adaptive candidate を評価するたびに `RemoteExperts::holds(l, e)` で問い合わせるため、初期化時の一覧を固定保存しない（CUDA/HIP 系 `engine/src/program/generate.cpp:10230-10243`、SYCL 系 `engine/sycl/src/program/generate.cpp:5767-5780`）。

有効時、主 cache に未常駐で利用カウントが閾値以上の候補を集める段階で、helper が保持中なら候補に加えない。CUDA/HIP 系の serve 用 blocking adaptive tier と asynchronous tier、非 serve の適応処理にこの判定がある（`engine/src/program/generate.cpp:15349-15379,15632-15653,24704-24745`）。SYCL 系も serve 用 blocking tier、asynchronous tier、非 serve の適応処理で同様に除外する（`engine/sycl/src/program/generate.cpp:8851-8877,9104-9125,13858-13895`）。その後の適応処理が選ぶ resident victim、入替数、コピー処理は既存の条件に従う。ルータの expert 選択・expert 計算そのものをこのフラグが変更する処理は見つからない。

## ログと測定値

この変数専用の有効・無効ログ、警告、終了経路はない。無効値でも警告は出ず、設定値によって adaptive tier の失敗処理が変わるコードもない。adaptive refill 自体の失敗は既存処理として `strata generate: an adaptive refill failed` などを出し、呼び出し側の失敗経路へ進む（CUDA/HIP 系 `engine/src/program/generate.cpp:24746-24750,24772-24782`、SYCL 系 `engine/sycl/src/program/generate.cpp:13896-13900,13915-13923`）。`STRATA_TRACE_ADAPT` が有効な場合の round / swap 数ログも一般の adaptive tier のログであり、この変数が除外した候補数は報告しない（CUDA/HIP 系 `engine/src/program/generate.cpp:24707-24717,24799-24801`、SYCL 系 `engine/sycl/src/program/generate.cpp:13861-13871,13945-13948`）。

この文書では性能値を記載しない。`docs/DISJOINT_EXPERT_CACHE.md` には過去の検証条件と結果があるが、同文書は公式 main への移植結果がその測定値を再測定したものではないと明記しており、現行 checkout の性能測定は本調査では行っていない。

## 根拠

- CUDA/HIP 系の読み取り、helper の live 判定: `engine/src/program/generate.cpp:10230-10243`。
- CUDA/HIP 系 blocking・async・非 serve の候補選別: `engine/src/program/generate.cpp:15349-15379,15632-15653,24704-24745`。
- SYCL 系の読み取り、helper の live 判定: `engine/sycl/src/program/generate.cpp:5767-5780`。
- SYCL 系 blocking・async・非 serve の候補選別: `engine/sycl/src/program/generate.cpp:8851-8877,9104-9125,13858-13895`。
- helper 保持判定の実装: `engine/include/strata/core/remote_experts.hpp:41-43`、`engine/sycl/include/strata/core/remote_experts.hpp:37-39`。
