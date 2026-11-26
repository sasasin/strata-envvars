# `STRATA_DF2_RING_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

DFlash2 drafter の会話再開用 ring log を無効化するスイッチです。通常は、DFlash2 が各 context 更新で K/V を作る前の量子化 activation row と scale をホスト側に記録し、会話の rewind・分岐・切替後に必要な ring 行を再構築します。無効時はこのログを記録・利用せず、再開時は従来の履歴照合規則で ring を継続するか cold start にします。設定は DFlash2 の ring 復元経路に作用し、DFlash2 の選択自体や別の drafter を有効化するものではありません（CUDA/HIP: `engine/src/core/dflash2.cpp:820-835,871-889,954-977`、SYCL: `engine/sycl/src/core/dflash2.cpp:215-225,633-655`）。

この環境変数は `Dflash2Drafter::alloc()` 中に読み取られます。CUDA/HIP では通常 load 時と clone の allocation 時、SYCL では drafter の allocation 時です。serve の各 request で参照される値ではありません（CUDA/HIP: `engine/src/core/dflash2.cpp:305-345,658-667,822-830`、SYCL: `engine/sycl/src/core/dflash2.cpp:168-225`）。

## 値と判定

両 backend とも `getenv` の結果が存在し、先頭 byte が文字 `'0'` の場合だけ無効化します。文字列全体は parse せず、`0` の後ろも検査しません。空文字は設定済みでも先頭 byte が終端文字なので無効化条件に当たらず、有効側です。大小文字・空白・boolean 表記の解釈はありません（CUDA/HIP: `engine/src/core/dflash2.cpp:825-827`、SYCL: `engine/sycl/src/core/dflash2.cpp:215-216`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP の drafter allocation | pinned staging の両領域を確保できれば有効。確保できなければ無効 | 空文字、`1`、`true`、`false`、` 0` | `0`、`0anything`、`00` |
| SYCL の drafter allocation | 有効 | 空文字、`1`、`true`、`false`、` 0` | `0`、`0anything`、`00` |
| CUDA split bridge の load | bridge が未設定値を `0` にするため無効 | 既存の値が先頭 `0` 以外なら有効 | 既存値の先頭が `0`、または未設定（bridge が `0` を設定） |

CUDA/HIP では `init_ring_log()` の初期値 `log_on_ = false` から始まり、変数の先頭が `0` でなければ pinned host staging を確保して、両方確保できた場合に有効になります。SYCL は `log_on_ = true` が初期値で、先頭 `0` の場合だけ無効化した後に host staging を確保します。したがって staging の確保失敗時の fallback も含め、未設定時の実効値は backend 間で同じではありません（`engine/include/strata/core/dflash2.hpp:252-258`、`engine/src/core/dflash2.cpp:822-834`、`engine/sycl/include/strata/core/dflash2.hpp:165-170`、`engine/sycl/src/core/dflash2.cpp:215-225`）。

この変数に対応する CLI 引数や別設定値による上書きは実装にありません。CUDA split bridge は Windows では未設定なら `_putenv_s(..., "0")`、それ以外では `setenv(..., "0", 0)` を呼びます。後者は既存値を上書きしない指定であり、Windows 側も `getenv` が null の場合に限って設定するため、利用者が設定した値は保持されます（`engine/src/split/src/df2_bridge.cpp:44-61`）。

## 有効になる条件

- DFlash2 がビルドに含まれ、実行時に DFlash2 drafter がロード・allocation されること。CUDA/HIP serve 側の request 処理は `STRATA_HAVE_DFLASH2` の compile guard 内です（`engine/src/program/generate.cpp:20170-20185`）。SYCL serve も `use_df2` の場合に request 開始時に `begin_request()` を呼びます（`engine/sycl/src/program/generate.cpp:11105-11118`）。DFlash2 を使わない CLI／モデルでは、この変数を読む DFlash2 allocation がなく、効果はありません。
- CUDA/HIP では `STRATA_DF2_RING_LOG` が先頭 `0` でなく、かつ pinned staging の `h_logq_` と `h_logd_` の両方を確保できること。確保に失敗すると `log_on_` が false になり、ring log は使われません（`engine/src/core/dflash2.cpp:822-834`）。
- SYCL では値の先頭が `0` でなく、host staging の両領域を確保できること。確保失敗時は部分確保を解放して ring log を無効化します（`engine/sycl/src/core/dflash2.cpp:215-225`）。
- ログの効果が現れるのは、記録済みの会話履歴を DFlash2 が再利用し、request の window に ring 上で欠けた行がある場合です。ログにない行は再構築できず、cold 扱いになります（CUDA/HIP: `engine/src/core/dflash2.cpp:954-977,1007-1034`、SYCL: `engine/sycl/src/core/dflash2.cpp:633-712`）。
- CUDA split bridge では環境未設定時に限り `0` を設定します。明示的な環境値がある場合はその値が DFlash2 allocation に渡ります（`engine/src/split/src/df2_bridge.cpp:49-61`）。

## 実行時の詳細

CUDA/HIP の `init_ring_log()` は drafter allocation 中に呼ばれます。先頭 `0` を見つけるとその場で戻り、pinned staging の割当てと有効化を行いません。その他の値では、activation codes と scales の staging を確保し、両方 non-null のときだけ `log_on_` を true にします。SYCL も `alloc()` 中に一度読み、同様に値を判定して staging を用意します。環境をプロセス実行中に変更しても既存 drafter の状態は変わりません。後から allocation される clone などは、その allocation 時点で環境を読みます（CUDA/HIP: `engine/src/core/dflash2.cpp:305-345,658-667,822-834`、SYCL: `engine/sycl/src/core/dflash2.cpp:168-225`）。

ログ有効時、context 処理は更新行の位置を記録し、GPU 処理後の量子化 codes と scales を lineage ごとのホストログへコピーします。serve の `begin_request()` は、履歴 token prefix が一致する live lineage または退避 lineage を探し、必要な ring 行をログから再構築します。無効時はこの探索・再構築経路を通らず、既存 history と resume prefix の共通部分を比較します。ring に古い行が残る stale 条件（ring の上端が共通 prefix を越え、共通 prefix が resume より短い場合）では epoch と ring 上端をリセットし、`cold` を返します（CUDA/HIP: `engine/src/core/dflash2.cpp:871-889,954-977`、SYCL: `engine/sycl/src/core/dflash2.cpp:558-579,633-655`）。

ログ有効時でも必要行がログにない場合は再構築されず、欠損行として扱われます。rebuild 処理自体が失敗すると stderr に `strata dflash2: <error>: the ring starts over for this request` を出して ring を invalid 化し、その window の行を欠損扱いにします（CUDA/HIP: `engine/src/core/dflash2.cpp:1007-1017`、SYCL: `engine/sycl/src/core/dflash2.cpp:685-695`）。別環境変数 `STRATA_DF2_LOG_MIB` は、設定され空でなければ allocation 時に `atoi` で読み込まれ、stash の MiB 上限を決めます。ring log の有効／無効判定を上書きしません（CUDA/HIP: `engine/src/core/dflash2.cpp:825-830`、SYCL: `engine/sycl/src/core/dflash2.cpp:215-220`）。

## ログと測定値

- CUDA/HIP で pinned staging の確保に失敗すると stderr に `strata dflash2: the ring log's staging does not fit in pinned memory: the log is off` を出します。SYCL では host staging の確保失敗時に `strata dflash2: the ring log's staging does not fit in host memory: the log is off` を出します（`engine/src/core/dflash2.cpp:828-834`、`engine/sycl/src/core/dflash2.cpp:217-225`）。
- serve は再構築行があれば `strata serve: DFlash2: ... context rows of the window rebuilt from the drafter's log ...` を stderr に出します。cold で欠損行が64以上の場合は、会話のログがないため最初の rounds は draft 品質が低くなる旨も出します。出力 token は同じと実装メッセージに記載されています（CUDA/HIP: `engine/src/program/generate.cpp:20174-20182`、SYCL: `engine/sycl/src/program/generate.cpp:11108-11116`）。
- `STRATA_DF2_RING_STATS` が設定されている場合、欠損位置や request ごとの再構築状況を追加で stderr に出します。未設定時はこれらの追加統計ログを抑制します（CUDA/HIP: `engine/src/core/dflash2.cpp:899,1018-1022`、SYCL: `engine/sycl/src/core/dflash2.cpp:593,696-700`）。
- `docs/DETAILS.md` の確認範囲に、この変数の値規則や性能測定値は見つかりませんでした。測定値は記載していません。

## 根拠

- `engine/src/core/dflash2.cpp:305-345,658-667,820-889,891-952,954-1034`
- `engine/include/strata/core/dflash2.hpp:94-128,245-270`
- `engine/sycl/src/core/dflash2.cpp:168-235,483-579,585-712`
- `engine/sycl/include/strata/core/dflash2.hpp:54-67,154-181`
- `engine/src/split/src/df2_bridge.cpp:44-61`
- `engine/src/program/generate.cpp:20170-20185`
- `engine/sycl/src/program/generate.cpp:11105-11118`
