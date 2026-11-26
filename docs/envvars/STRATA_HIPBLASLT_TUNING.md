# `STRATA_HIPBLASLT_TUNING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の prefill GEMM で使う hipBLASLt tuning table のファイルパスを指定する。値が空でなければそのパスの表をロードし、表の shape ごとの solution を実際の GEMM に適用する。値が未設定または空文字なら、HIP エンジンは `STRATA_HIPBLASLT_TABLE` と実行ファイル隣の `tuning/` を使う経路を判定する。どちらの経路も使わない場合や、表・solution が使えない場合は hipBLASEx に戻る。表は入力 dtype と行列 shape に対する選択を変えるもので、すべての GEMM を一律に置き換えるものではない（`engine/src/prefill/gemm.cu:284-300,392-399,488-538,793-799,854-888`）。

Strata 所有コードでは HIP の通常エンジン実装（`engine/src/prefill/gemm.cu`）と SYCL ツリーの実装（`engine/sycl/src/prefill/gemm.dp.cpp`）が値を直接読み取る。後者も HIPBLASLT build macro が有効な箇所で state を作り、BF16/F16 GEMM から試行する。候補名の登録・文書・テストでの参照だけでなく、製品コードに読み取り箇所がある（`engine/sycl/src/prefill/gemm.dp.cpp:196-230,428-431,497-499,890-895,968-973`）。

## 値と判定

| 実行経路 | 未設定 | 空文字 | 設定時に有効になる値 | 無効値・不適合時 |
|---|---|---|---|---|
| HIP (`engine/src/prefill/gemm.cu`) | `STRATA_HIPBLASLT_TABLE` を見て同梱表の選択を判定 | 未設定と同じ | 空でない文字列をそのままファイルパスとして読む。値の真偽・数値・大文字小文字の parse はしない。空白の trim もない | `0`、`false`、`on` も特別扱いされずファイル名。存在しない、読めない、形式・GPU arch・hipBLASLt version が合わない表は load 失敗して hipBLASEx を使う |
| SYCL ツリーの HIPBLASLT 対応箇所 | state を作らない | state を作らない | 空でない文字列をファイルパスとして読む | 読込・検証失敗時は理由を出して hipBLASEx を使う |

HIP 実装では `std::getenv` の戻り値が null か、先頭文字が NUL かだけを判定する（`engine/src/prefill/gemm.cu:284-300`）。従って例として `unset` と `STRATA_HIPBLASLT_TUNING=''` は同じく自動選択側へ進み、`/path/table.txt` はパス、`0` や `false` はその名前の相対パス、空白だけの値も空でないパスとなる。`0anything` も同様にファイルパスである。相対パスはエンジンの current working directory 基準で開かれる。SYCL 側も null / 空文字だけを除外し、同じく値を path として `TuningTable::load` に渡す（`engine/sycl/src/prefill/gemm.dp.cpp:196-198,223-230`）。

HIP 経路で指定された表は、ヘッダーが `STRATA_HIPBLASLT_TUNING_V1` または `..._V2` であること、architecture が実行 GPU と一致するか許可された同一世代 family であること、version が一致すること（V2 は双方 `100500` 以上なら version 差を許す）を検証する。各行は dtype `f16` / `bf16`、正の `n`,`k`,`t_bucket`、`ldy >= n`、非負 solution ID を要求し、重複 key や余分な列も拒否する。失敗時はエラー理由と `using hipBLASEx` を stderr に出す（`engine/src/prefill/hipblaslt_tuning.hpp:27-121`）。

CLI 引数でこのパスを直接指定する処理は確認できなかった。Server の run config は `env` 辞書で値を渡す。engine 起動環境は親環境のコピーを作った後に `cfg.env` を反映するため、同名の `cfg.env` があれば子エンジンでは親環境の値を上書きする（`terminal/serve/server.py:4007-4028`）。Server の表選択ログ用 `user_choice` は親環境を先に見てから config の `env` を見て空白を trim するが、engine にセットする `child_env` の値にはその trim は適用しない（`terminal/strata_control/hipblaslt_tuning.py:187-194,220-228`; `terminal/serve/server.py:4027-4028`）。

## 有効になる条件

- HIP エンジンが build に含む `STRATA_HIPBLASLT_AVAILABLE` の機能が必要。HIP 以外の CUDA 等ではこの経路を使わない（`engine/src/prefill/gemm.cu:757-759,793-799,873-878`）。SYCL ソースでは `__HIPCC__` と `STRATA_HIPBLASLT_AVAILABLE` の条件下で同じ state を初期化・呼び出す箇所がある（`engine/sycl/src/prefill/gemm.dp.cpp:428-431,497-499,890-895,968-973`）。
- GPU/runtime の問い合わせと hipBLASLt handle/version の取得に成功し、表がその GPU architecture と hipBLASLt version に適合する必要がある。これらに失敗すると hipBLASEx へ進む（`engine/src/prefill/gemm.cu:307-325,392-399`; 表の照合は `engine/src/prefill/hipblaslt_tuning.hpp:49-79`）。
- 表に dtype と `n`,`k`,`ldy` が一致する行が必要。`T` は表の bucket のうち距離が最小のものを選び、同距離なら小さい bucket を選ぶ。該当行がないときはその GEMM だけ hipBLASEx に fallback する（`engine/src/prefill/hipblaslt_tuning.hpp:124-136`; `engine/src/prefill/gemm.cu:411-420,488-500`）。
- 既定の HIP 経路では `STRATA_HIPBLASLT_TUNING` が空の場合に限り `STRATA_HIPBLASLT_TABLE` を評価する。`off`, `0`, `no`, `false`, `none`, `disable`, `disabled`（前後空白除去後、小文字化）は同梱表を使わない。`on`, `1`, `yes`, `true`, `force`, `enable`, `enabled` は architecture 対応の同梱表を強制する。それ以外・未設定・`auto` は auto 扱いで、gfx11 WMMA 対応 arch（ただし `STRATA_GFX11_DEFAULTS` の先頭文字が `0` なら除外）または gfx1151 は自動対象、その他は明示的な on が必要。gfx1103 は Linux で CWSR が有効と判明した場合 auto では skip し、on なら強制する（`engine/src/prefill/gemm.cu:288-300,327-355`）。
- この自動選択経路では、同梱の `tuning/<arch>-hipblaslt-<version>.txt` が必要。完全一致版がなければ hipBLASLt `100500` 以上に限り、該当 arch の V2 表から version `>=100500` のうち大きい版を探す。見つからない場合は hipBLASLt state を作らない（`engine/src/prefill/gemm.cu:357-385`）。ただしこの探索条件は明示パスの値には適用されず、明示パスを直接 load する。
- HIP prefill の BF16/F16 GEMM から呼ばれる。呼び出し前に WMMA などの別経路が処理を終えた shape ではこの表を使わない（例: `engine/src/prefill/gemm.cu:854-874,890-896,947-975`）。

## 実行時の詳細

HIP では `Gemm::init` / `Gemm::init_external` 時に `create_hipblaslt_state` が実行され、その時点で環境値を読み、handle・device・version を照会して表をロードする。state は `Gemm` インスタンスに保持され、後続 GEMM ごとに環境変数を読み直さない。algorithm 解決結果は `(dtype,T,N,K,ldy,beta)` key で state 内 cache に保存する。したがってプロセス起動後の環境変更は既存 `Gemm` の table/state に反映されない（`engine/src/prefill/gemm.cu:284-300,392-400,402-420,757-799,854-878`）。SYCL 側も `Gemm` 初期化で state を作る（`engine/sycl/src/prefill/gemm.dp.cpp:196-230,404-431,456-499`）。

GEMM 呼び出し時、table row の solution が hipBLASLt に存在しない、kernel name が V2 の期待値と異なる、実 shape をサポートしない、または必要 workspace が確保量を超える場合、その呼び出しは hipBLASEx へ戻る。該当 shape / solution の解決結果は cache される。hipBLASLt の起動失敗は stderr に status と shape を出し shape を外して fallback する。ただし `beta != 0` かつ prelaunch failure と判定されない失敗では `refusing a fallback...` を出して `exit(1)` する（`engine/src/prefill/gemm.cu:428-474,488-538`; V2 kernel name 判定は `engine/src/prefill/gemm.cu:440-452`）。

## ログと測定値

表の load 成功時は stderr に `prefill gemm: hipBLASLt tuning enabled (%zu rows, %s, version %d)` を出す。失敗時は `prefill gemm: <理由>; using hipBLASEx`。gfx1103 の CWSR 条件による skip / 警告はコード中の `prefill gemm: gfx1103 hipBLASLt tuning table skipped...` または `prefill gemm: WARNING: loading...` の文言で出る（`engine/src/prefill/gemm.cu:352-355,388-399`）。

`STRATA_HIPBLASLT_VERBOSE` が設定されている場合（空文字を含む）は、shape に行がない、solution が使えない、workspace 不足等の fallback 理由や、選ばれた solution・shape・workspace を stderr に追加する。未設定ならこれらの詳細行は抑制される（`engine/src/prefill/gemm.cu:411-420,428-474,502-509`）。

Strata のソースコメント・設計資料に記載された性能値は、対象環境・条件の範囲をこの文書で一般化できる十分な測定条件が揃わないため記載しない。

## 根拠

- `engine/src/prefill/gemm.cu:284-399` — HIP 実装の変数読取、同梱表選択、表 load と初期化ログ。
- `engine/src/prefill/gemm.cu:402-538` — solution の解決/cache、GEMM への適用、fallback と終了経路。
- `engine/src/prefill/hipblaslt_tuning.hpp:27-136` — 表形式・arch/version/key 検証と row 選択。
- `engine/sycl/src/prefill/gemm.dp.cpp:196-230,428-431,497-499,890-895,968-973` — SYCL ツリーの読取、初期化と呼出し。
- `terminal/strata_control/hipblaslt_tuning.py:160-194,220-290` — Server 側の別スイッチ、明示指定の判定、同梱表選択。
- `terminal/serve/server.py:4007-4028` — Server 子 engine の環境構築と config `env` の反映。
